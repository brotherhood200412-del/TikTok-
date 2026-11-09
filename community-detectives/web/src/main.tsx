import { StrictMode, Suspense, lazy } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { FullPageMessage, Spinner, ToastProvider } from './components/ui';
import './styles.css';

const Landing = lazy(() => import('./pages/Landing'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Control = lazy(() => import('./pages/Control'));
const Play = lazy(() => import('./pages/Play'));
const Overlay = lazy(() => import('./pages/Overlay'));
const Admin = lazy(() => import('./pages/Admin'));

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <Suspense fallback={<FullPageMessage title=""><Spinner /></FullPageMessage>}>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/control/:id" element={<Control />} />
            <Route path="/play/:code" element={<Play />} />
            <Route path="/overlay/:token" element={<Overlay />} />
            <Route path="/admin" element={<Admin />} />
            <Route path="*" element={<FullPageMessage title="Seite nicht gefunden" />} />
          </Routes>
        </Suspense>
      </ToastProvider>
    </BrowserRouter>
  </StrictMode>,
);
