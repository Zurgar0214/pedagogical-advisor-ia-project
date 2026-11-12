# Frontend — Asesor Pedagógico Inteligente

Vite + React + TypeScript + Tailwind CSS 4 + React Router + `@xyflow/react`.

```bash
npm install
cp .env.example .env   # opcional
npm run dev            # http://localhost:5173 (proxy /api -> http://localhost:8000)
npm run build
npm run lint
```

- `VITE_API_URL`: base de la API (por defecto `/api`).
- Foto del equipo: `public/equipo/juan-diego.jpg` (si no existe se muestran las iniciales "JV").
- Páginas: Proyecto (RF-11) completa; el resto son marcadores con su ID de requisito.
