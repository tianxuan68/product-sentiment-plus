# 澄见 · 普通用户首页壳子

独立于原 Vue 管理后台的 React + TypeScript + Tailwind CSS + React Router + Framer Motion 前端壳子。

## 启动

```bash
cd front/home-shell
npm install
npm run dev
```

生产构建：`npm run build`，构建产物在 `dist/`。

演示登录账号：`dxx` / `dxx123456@`。

## API 接入

默认使用 Mock 数据。复制 `.env.example` 为 `.env.local` 后设置：

```bash
VITE_API_BASE_URL=http://localhost:8000
VITE_USE_MOCK=false
```

统一请求封装在 `src/api/apiClient.ts`；业务调用在 `src/services/backendService.ts`。组件不直接使用 `fetch` 或 `axios`。

当前预留接口：

- `GET /api/user/info`
- `GET /api/insights`
- `POST /api/auth/login`

后续可在 service 层增加产品列表、统计数据、动态内容等接口，并保持页面组件只消费类型化数据。
