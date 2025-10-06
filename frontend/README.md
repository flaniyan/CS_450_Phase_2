# ACME Registry Frontend

React + Vite frontend for the ACME Trustworthy Package Registry.

## 🚀 Quick Start

### Install Dependencies
```bash
npm install
```

### Run Development Server
```bash
npm run dev
```
The app will be available at `http://localhost:3000`

### Build for Production
```bash
npm run build
```

### Preview Production Build
```bash
npm run preview
```

## 📁 Project Structure

```
frontend/
├── src/
│   ├── pages/          # Route pages
│   ├── components/     # Reusable UI components
│   ├── services/       # API client
│   ├── App.tsx         # Main app component
│   └── main.tsx        # Entry point
├── tests/              # Selenium tests
├── package.json
└── vite.config.ts
```

## 🧪 Testing

### Run Unit Tests
```bash
npm test
```

### Run Selenium E2E Tests
```bash
npm run test:selenium
```

## 🎨 Features

- ✅ React + TypeScript
- ✅ Chakra UI for styling
- ✅ React Router for navigation
- ✅ Axios for API calls
- ✅ Full ADA compliance
- ✅ Responsive design

## 📡 API Integration

The frontend expects a backend API at `http://localhost:8080`. Configure the proxy in `vite.config.ts` if needed.

## 🔒 Environment Variables

Create a `.env` file if you need custom configuration:
```
VITE_API_URL=http://localhost:8080
```

