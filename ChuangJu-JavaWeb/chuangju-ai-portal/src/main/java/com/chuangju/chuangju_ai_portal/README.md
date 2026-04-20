    /**
     * 捕获所有不包含文件扩展名的路径，并将其转发到 /index.html。
     * 这样做的目的是确保当用户直接访问像 /gallery 或 /analysis 这样的深层链接时，
     * 或者刷新页面时，始终由前端Vue应用来处理路由，而不是后端返回404。
     *
     * value = { "/", "/{path:[^\\.]*}", "/**/{path:[^\\.]*}" }:
     * - "/" : 匹配根路径。
     * - "/{path:[^\\.]*}" : 匹配任何不含点号（即没有文件扩展名）的单层路径。
     * - "/**/{path:[^\\.]*}" : 匹配任何不含点号的多层嵌套路径。
     *
     * return "forward:/index.html";
     * Spring Boot会将请求内部转发到位于 src/main/resources/static/index.html 的文件。
     */
