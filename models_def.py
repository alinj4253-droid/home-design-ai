# models_def.py 

import torch.nn as nn
import timm

class MultiTaskStyleRoomClassifier(nn.Module):
    def __init__(self, num_styles: int, num_room_types: int, model_name: str = 'vit_base_patch16_384'):
        super().__init__()
        self.backbone = timm.create_model(model_name, pretrained=True, num_classes=0)
        feature_dim = self.backbone.num_features
        self.style_head = nn.Sequential(
            nn.LayerNorm(feature_dim), nn.Linear(feature_dim, 512),
            nn.GELU(), nn.Dropout(0.5), nn.Linear(512, num_styles)
        )
        self.room_type_head = nn.Sequential(
            nn.LayerNorm(feature_dim), nn.Linear(feature_dim, 512),
            nn.GELU(), nn.Dropout(0.5), nn.Linear(512, num_room_types)
        )
    def forward(self, x):
        features = self.backbone(x)
        return self.style_head(features), self.room_type_head(features)

class StyleClassifier(nn.Module):
    def __init__(self, num_classes: int, model_name: str, pretrained: bool = True):
        super().__init__()
        self.backbone = timm.create_model(model_name, pretrained=pretrained, num_classes=0)
        feature_dim = self.backbone.num_features
        self.classifier = nn.Sequential(
            nn.LayerNorm(feature_dim), nn.Linear(feature_dim, 512),
            nn.GELU(), nn.Dropout(0.5), nn.Linear(512, num_classes)
        )
    def forward(self, x):
        return self.classifier(self.backbone(x))