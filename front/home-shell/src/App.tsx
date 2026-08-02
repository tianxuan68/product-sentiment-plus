import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Dashboard } from './pages/Dashboard';
import { Home } from './pages/Home';
import { Login } from './pages/Login';
import './styles.css';
export default function App() { return <BrowserRouter><Routes><Route path="/" element={<Home />} /><Route path="/login" element={<Login />} /><Route path="/dashboard" element={<Dashboard />} /><Route path="/explore" element={<Home />} /><Route path="/solutions" element={<Home />} /><Route path="/about" element={<Home />} /><Route path="*" element={<Navigate to="/" replace />} /></Routes></BrowserRouter>; }
