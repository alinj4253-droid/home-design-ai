# 2_train_all_models.py

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
import json
import argparse
from tqdm import tqdm
from PIL import Image
import torchvision.transforms as transforms
from pathlib import Path
from collections import Counter
import torch.nn.functional as F
from torch.amp import GradScaler, autocast
from packaging import version

import config
from models_def import MultiTaskStyleRoomClassifier, StyleClassifier

Image.MAX_IMAGE_PIXELS = None

class FocalLoss(nn.Module):
    def __init__(self, alpha=1, gamma=2): super().__init__(); self.alpha, self.gamma = alpha, gamma
    def forward(self, inputs, targets):
        ce_loss = F.cross_entropy(inputs, targets, reduction='none', ignore_index=-100)
        pt = torch.exp(-ce_loss); focal_loss = self.alpha * (1 - pt)**self.gamma * ce_loss
        valid_loss = focal_loss[targets != -100]
        return valid_loss.mean() if valid_loss.numel() > 0 else torch.tensor(0.0, device=inputs.device)

class BaseDataset(Dataset):
    def __init__(self, annotations_file=None, base_dir=None, transform=None, annotations_list=None):
        if annotations_list is not None: self.annotations = annotations_list
        elif annotations_file is not None:
            with open(annotations_file, 'r', encoding='utf-8') as f: self.annotations = json.load(f)
        else: raise ValueError("必须提供 'annotations_file' 或 'annotations_list'")
        self.base_dir, self.transform = Path(base_dir), transform
    def __len__(self): return len(self.annotations)
    def __getitem__(self, idx):
        ann = self.annotations[idx]; img_path = self.base_dir / ann['image_path']
        try: image = Image.open(img_path).convert('RGB')
        except Exception: image = Image.new('RGB', (384, 384), color='black')
        if self.transform: image = self.transform(image)
        return image, ann

class MultiTaskDataset(BaseDataset):
    def __init__(self, annotations_file, base_dir, transform=None):
        super().__init__(annotations_file=annotations_file, base_dir=base_dir, transform=transform)
        styles=sorted(list(set(ann['style'] for ann in self.annotations if ann.get('style')))); room_types=sorted(list(set(ann['room_type'] for ann in self.annotations if ann.get('room_type'))))
        self.style_to_idx={n:i for i,n in enumerate(styles)}; self.room_type_to_idx={n:i for i,n in enumerate(room_types)}
        self.style_counts=Counter(self.style_to_idx[ann['style']] for ann in self.annotations if ann.get('style')); self.room_type_counts=Counter(self.room_type_to_idx[ann['room_type']] for ann in self.annotations if ann.get('room_type'))
        print(f"主线数据集初始化: {len(self)}样本。风格:{len(styles)}种。房间类型:{len(room_types)}种。")
    def __getitem__(self, idx):
        image, ann = super().__getitem__(idx); return image, self.style_to_idx.get(ann.get('style'), -100), self.room_type_to_idx.get(ann.get('room_type'), -100)

class SingleTaskDataset(BaseDataset):
    def __init__(self, annotations_file=None, base_dir=None, transform=None, annotations_list=None):
        super().__init__(annotations_file=annotations_file, base_dir=base_dir, transform=transform, annotations_list=annotations_list)
        styles=sorted(list(set([ann['style'] for ann in self.annotations]))); self.style_to_idx={name:i for i,name in enumerate(styles)}
        self.targets=[self.style_to_idx[ann['style']] for ann in self.annotations]; self.style_counts=Counter(self.targets)
    def __getitem__(self, idx): image, ann=super().__getitem__(idx); return image, self.style_to_idx[ann['style']]

class SystemTrainer:
    def __init__(self, trainer_config):
        self.config, self.device = trainer_config, torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        Path(self.config['model_output_dir']).mkdir(parents=True, exist_ok=True)
        self.furniture_types = ['bed', 'sofa', 'chair']
        print(f"系统训练器初始化完成，设备: {self.device}")
        
        self.use_torch_compile = version.parse(torch.__version__) >= version.parse("2.0.0")
        if self.use_torch_compile:
            print("PyTorch 2.0+ 已检测到，将启用 'torch.compile' 以获得最大加速。")
        else:
            print("PyTorch 版本低于 2.0，将跳过 'torch.compile'。")

    def get_transforms(self, img_size, is_training=True):
        if is_training: return transforms.Compose([transforms.Resize((int(img_size*1.15),int(img_size*1.15))), transforms.RandomCrop(img_size), transforms.RandomHorizontalFlip(p=0.5), transforms.TrivialAugmentWide(), transforms.ToTensor(), transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225]), transforms.RandomErasing(p=0.25)])
        else: return transforms.Compose([transforms.Resize((img_size,img_size)), transforms.ToTensor(), transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225])])

    def _run_multitask_training_loop(self, model, train_loader, val_loader, optimizer, scheduler, criterion_style, criterion_room_type):
        best_val_acc, patience_counter = 0.0, 0; epochs = self.config['epochs']; patience = self.config['patience']
        
        scaler = GradScaler(enabled=self.device.type == 'cuda')

        for epoch in range(epochs):
            model.train()
            for images, style_labels, room_type_labels in tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs}"):
                images, style_labels, room_type_labels = images.to(self.device), style_labels.to(self.device), room_type_labels.to(self.device)
                optimizer.zero_grad(set_to_none=True)

                with autocast(device_type=self.device.type, dtype=torch.float16, enabled=self.device.type == 'cuda'):
                    style_logits, room_type_logits = model(images)
                    loss_s = criterion_style(style_logits, style_labels)
                    loss_r = criterion_room_type(room_type_logits, room_type_labels)
                    loss = loss_s + loss_r
                
                if isinstance(loss, torch.Tensor):
                    scaler.scale(loss).backward()
                    scaler.step(optimizer)
                    scaler.update()

            model.eval()
            style_correct, style_total, room_type_correct, room_type_total = 0, 0, 0, 0
            with torch.no_grad():
                for images, style_labels, room_type_labels in val_loader:
                    images, sl, rl = images.to(self.device), style_labels.to(self.device), room_type_labels.to(self.device)
                    with autocast(device_type=self.device.type, dtype=torch.float16, enabled=self.device.type == 'cuda'):
                        style_logits, room_logits = model(images)
                    
                    valid_s = (sl != -100); style_correct += (style_logits.argmax(1)[valid_s] == sl[valid_s]).sum().item(); style_total += valid_s.sum().item()
                    valid_r = (rl != -100); room_type_correct += (room_logits.argmax(1)[valid_r] == rl[valid_r]).sum().item(); room_type_total += valid_r.sum().item()
            
            style_acc = (100 * style_correct / style_total if style_total > 0 else 0)
            room_type_acc = (100 * room_type_correct / room_type_total if room_type_total > 0 else 0)
            avg_acc = (style_acc + room_type_acc) / 2
            print(f"Epoch {epoch+1}: Style Acc: {style_acc:.2f}% | Room Type Acc: {room_type_acc:.2f}% | Avg Acc: {avg_acc:.2f}%")
            scheduler.step(avg_acc)
            
            if avg_acc > best_val_acc:
                best_val_acc, patience_counter = avg_acc, 0
                model_to_save = model._orig_mod if self.use_torch_compile and hasattr(model, '_orig_mod') else model
                torch.save(model_to_save.state_dict(), Path(self.config['model_output_dir']) / 'multitask_model_best.pth')
                print(f"  =>  新的最佳主线模型已保存，平均准确率: {best_val_acc:.2f}%")
            else:
                patience_counter += 1
                if patience_counter >= patience: print(f"  =>  早停触发！"); break
        print(f"\n 主线任务模型训练完成！")

    def train_main_task(self):
        print(f"\n{'='*60}\n 开始训练主线任务模型 (房间类型+整体风格)\n{'='*60}")
        ann_dir = Path(self.config['annotations_dir']); base_data_dir_main = str(config.BASE_DATA_DIR)
        train_dataset = MultiTaskDataset(ann_dir/'main_task'/'train_multitask.json', base_data_dir_main, self.get_transforms(384, True))
        val_dataset = MultiTaskDataset(ann_dir/'main_task'/'val_multitask.json', base_data_dir_main, self.get_transforms(384, False))
        train_loader = DataLoader(train_dataset, self.config['batch_size'], shuffle=True, num_workers=4, pin_memory=True)
        val_loader = DataLoader(val_dataset, self.config['batch_size'], shuffle=False, num_workers=4, pin_memory=True)
        model = MultiTaskStyleRoomClassifier(len(train_dataset.style_to_idx), len(train_dataset.room_type_to_idx), model_name=self.config['global_model_name']).to(self.device)
        
        if self.use_torch_compile and self.device.type == 'cuda':
            model = torch.compile(model)

        total_samples = len(train_dataset.annotations)
        style_weights = torch.tensor([total_samples / train_dataset.style_counts.get(i, total_samples) for i in range(len(train_dataset.style_to_idx))], dtype=torch.float).to(self.device)
        room_type_weights = torch.tensor([total_samples / train_dataset.room_type_counts.get(i, total_samples) for i in range(len(train_dataset.room_type_to_idx))], dtype=torch.float).to(self.device)
        optimizer = optim.AdamW(model.parameters(), lr=self.config['main_lr'], weight_decay=0.01)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'max', patience=5, factor=0.5)
        criterion_style = nn.CrossEntropyLoss(weight=style_weights, ignore_index=-100)
        criterion_room_type = nn.CrossEntropyLoss(weight=room_type_weights, ignore_index=-100)
        self._run_multitask_training_loop(model, train_loader, val_loader, optimizer, scheduler, criterion_style, criterion_room_type)

    def _run_training_loop(self, model, model_save_name, train_loader, val_loader, optimizer, scheduler, criterion, epochs, patience, stage_name):
        best_val_acc=0.0; patience_counter=0
        output_dir=Path(self.config['model_output_dir']); best_path=output_dir/f'{model_save_name}_best.pth'
        
        scaler = GradScaler(enabled=self.device.type == 'cuda')
        
        for epoch in range(epochs):
            model.train()
            for images, labels in tqdm(train_loader, desc=f'Epoch {epoch+1}/{epochs} {stage_name}', leave=False):
                images, labels = images.to(self.device), labels.to(self.device)
                optimizer.zero_grad(set_to_none=True)

                with autocast(device_type=self.device.type, dtype=torch.float16, enabled=self.device.type == 'cuda'):
                    outputs = model(images)
                    loss = criterion(outputs, labels)

                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()

            model.eval()
            val_correct, val_total = 0, 0
            with torch.no_grad():
                for images, labels in val_loader:
                    images, labels = images.to(self.device), labels.to(self.device)
                    with autocast(device_type=self.device.type, dtype=torch.float16, enabled=self.device.type == 'cuda'):
                        outputs = model(images)
                    val_correct += (outputs.argmax(1) == labels).sum().item(); val_total += labels.size(0)
            
            val_acc = 100. * val_correct / val_total if val_total > 0 else 0

            if isinstance(scheduler, torch.optim.lr_scheduler.ReduceLROnPlateau):
                scheduler.step(val_acc)
            else:
                scheduler.step()

            print(f'Epoch {epoch+1} {stage_name}: Val Acc: {val_acc:.2f}% | LR: {optimizer.param_groups[0]["lr"]:.7f}')
            
            if val_acc > best_val_acc:
                best_val_acc, patience_counter = val_acc, 0
                model_to_save = model._orig_mod if self.use_torch_compile and hasattr(model, '_orig_mod') else model
                torch.save({'model_state_dict': model_to_save.state_dict(), 'val_accuracy': val_acc}, best_path)
                print(f"          =>  {stage_name} 新的最佳模型已保存，准确率: {best_val_acc:.2f}%")
            else:
                patience_counter += 1
                if patience_counter >= patience: print(f"          =>  {stage_name} 早停触发"); break

        final_path = output_dir / f'{model_save_name}_classifier.pth'
        if best_path.exists():
            checkpoint = torch.load(best_path, map_location=self.device)
            model_to_load = model._orig_mod if self.use_torch_compile and hasattr(model, '_orig_mod') else model
            model_to_load.load_state_dict(checkpoint['model_state_dict'])
            torch.save(checkpoint, final_path)
            print(f" 已将最佳模型保存为最终文件: {final_path}")

    def train_sideline_task(self):
        furniture_to_train=[self.config['furniture_type']] if self.config.get('furniture_type') else self.furniture_types
        ann_dir=Path(self.config['annotations_dir']); train_ann_path=ann_dir/'sideline_task'/'train_local.json'; val_ann_path=ann_dir/'sideline_task'/'val_local.json'
        print("正在从JSON文件加载并预处理所有副线任务标注...")
        with open(train_ann_path, 'r', encoding='utf-8') as f: all_train_anns = json.load(f)
        with open(val_ann_path, 'r', encoding='utf-8') as f: all_val_anns = json.load(f)
        train_anns_by_type={ft: [] for ft in self.furniture_types}; val_anns_by_type={ft: [] for ft in self.furniture_types}
        for ann in all_train_anns:
            if ann.get('furniture_type') in train_anns_by_type: train_anns_by_type[ann['furniture_type']].append(ann)
        for ann in all_val_anns:
            if ann.get('furniture_type') in val_anns_by_type: val_anns_by_type[ann['furniture_type']].append(ann)
        print("✓ 副线任务标注预处理完成。")
        for furniture_type in furniture_to_train:
            print(f"\n{'='*60}\n 开始训练副线任务模型 ({furniture_type.upper()} 风格分类器)\n{'='*60}")
            train_anns=train_anns_by_type.get(furniture_type, []); val_anns=val_anns_by_type.get(furniture_type, [])
            if len(train_anns) < 20: print(f"样本太少（{len(train_anns)}），跳过 {furniture_type}"); continue
            train_dataset=SingleTaskDataset(base_dir=self.config['base_data_dir'], annotations_list=train_anns, transform=self.get_transforms(224, True))
            val_dataset=SingleTaskDataset(base_dir=self.config['base_data_dir'], annotations_list=val_anns, transform=self.get_transforms(224, False))
            sampler=WeightedRandomSampler([1.0/train_dataset.style_counts[t] for t in train_dataset.targets], len(train_dataset.targets), True)
            train_loader=DataLoader(train_dataset, self.config['batch_size'], sampler=sampler, num_workers=4); val_loader=DataLoader(val_dataset, self.config['batch_size'], shuffle=False, num_workers=4)
            model=StyleClassifier(len(train_dataset.style_to_idx), self.config['local_model_name']).to(self.device)
            
            if self.use_torch_compile and self.device.type == 'cuda':
                model = torch.compile(model)
            
            criterion=FocalLoss()
            print(f"开始为 {furniture_type} 进行两阶段微调...")
            model_to_modify = model._orig_mod if self.use_torch_compile and hasattr(model, '_orig_mod') else model
            for p in model_to_modify.backbone.parameters(): p.requires_grad=False
            optimizer_head=optim.AdamW(model_to_modify.classifier.parameters(), lr=self.config['head_lr']); scheduler_head=optim.lr_scheduler.CosineAnnealingLR(optimizer_head, T_max=5)
            self._run_training_loop(model, furniture_type, train_loader, val_loader, optimizer_head, scheduler_head, criterion, 5, 3, "[Head-Train]")

            for p in model.parameters(): p.requires_grad=True 
            optimizer_ft=optim.AdamW([{'params': model_to_modify.backbone.parameters(), 'lr': self.config['main_lr'] / 10}, {'params':model_to_modify.classifier.parameters(),'lr':self.config['main_lr']}], weight_decay=0.05)
            scheduler_ft=optim.lr_scheduler.CosineAnnealingLR(optimizer_ft, T_max=self.config['epochs'])
            self._run_training_loop(model, furniture_type, train_loader, val_loader, optimizer_ft, scheduler_ft, criterion, self.config['epochs'], self.config['patience'], "[Fine-Tune]")
        print(f"\n 副线任务模型训练完成！")
    def run(self):
        if self.config['module'] in ['all', 'main']: self.train_main_task()
        if self.config['module'] in ['all', 'sideline']: self.train_sideline_task()
        print("\n" + "="*50 + "\n 所有训练任务完成！\n" + "="*50)

def main():
    parser=argparse.ArgumentParser(description='第二步：模型训练')
    parser.add_argument('--base_data_dir',type=str,default=str(config.GENERATED_LOCAL_DIR)); parser.add_argument('--annotations_dir',type=str,default=str(config.ANNOTATIONS_OUTPUT_DIR))
    parser.add_argument('--model_output_dir',type=str,default=str(config.MODEL_OUTPUT_DIR)); parser.add_argument('--module',type=str,choices=['main','sideline','all'],default='all')
    parser.add_argument('--furniture_type',type=str,choices=['bed','sofa','chair']); parser.add_argument('--local_model_name',type=str,default=config.LOCAL_TASK_MODEL_NAME)
    parser.add_argument('--global_model_name',type=str,default=config.MAIN_TASK_MODEL_NAME); parser.add_argument('--epochs',type=int,default=config.EPOCHS)
    parser.add_argument('--batch_size',type=int,default=config.BATCH_SIZE); parser.add_argument('--head_lr',type=float,default=config.HEAD_LR)
    parser.add_argument('--main_lr',type=float,default=config.MAIN_LR); parser.add_argument('--patience',type=int,default=config.PATIENCE,help='早停的耐心轮数')
    args=vars(parser.parse_args())
    print(" 训练配置: "); [print(f"   - {k}: {v}") for k,v in args.items()]
    trainer=SystemTrainer(args); trainer.run()

if __name__ == "__main__":
    main()