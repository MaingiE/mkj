# KYISA Frontend — React SPA

Modern React frontend for the Kenya Youth Interschool Sports Association Competition Management System.

## Tech Stack

- **React 18** with Vite 6
- **Tailwind CSS v4** (dark theme: `#0a0a0a` + teal `#20b2aa`)
- **Framer Motion** for animations
- **React Router v7** for client-side routing
- **Axios** with JWT interceptors for API communication
- **Recharts** for data visualisation
- **Heroicons v2** for icons

## Development

```bash
# Install dependencies
npm install

# Start dev server (proxies API calls to Django at :8000)
npm run dev
```

The Vite dev server runs on `http://localhost:5173` and proxies all `/api/*` and `/media/*` requests to Django on port 8000.

### Run both servers together:

**Terminal 1 — Django API:**
```bash
cd ..
python manage.py runserver 8000
```

**Terminal 2 — Vite frontend:**
```bash
npm run dev
```

## Production Build

```bash
npm run build
```

This outputs to `dist/`. Django serves the SPA at `/app/` via the catch-all view in `kyisa_cms/spa_views.py`.

## Project Structure

```
src/
├── api/               # Axios client + API endpoint methods
├── components/
│   ├── layout/        # Navbar, Sidebar, PublicLayout, PortalLayout
│   └── ui/            # Button, Card, Badge, Input, Modal, StatCard, Spinner
├── contexts/          # AuthContext (JWT state, role checks)
├── hooks/             # useFetch, useMutation, useDebounce
├── pages/             # All page components (lazy-loaded)
├── utils/             # Formatters, constants
├── App.jsx            # Route definitions
├── index.css          # Tailwind + custom theme
└── main.jsx           # App entry point
```

## Design Tokens

| Token       | Value     | Usage               |
|-------------|-----------|---------------------|
| brand-900   | #0a0a0a   | Page background     |
| accent      | #20b2aa   | Primary teal accent |
| surface     | #111111   | Card backgrounds    |
| border      | #2a2a2a   | Borders & dividers  |

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
