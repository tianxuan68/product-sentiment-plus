import { Menu, X } from 'lucide-react';
import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ActionButton } from './ActionButton';

export function Navbar() { const [open, setOpen] = useState(false); const location = useLocation(); const links = [['首页', '/'], ['产品介绍', '/explore'], ['解决方案', '/solutions'], ['关于我们', '/about']]; return <header className="site-nav"><Link to="/" className="brand-mark"><span className="brand-orb">✦</span><span>澄见 <small>INSIGHT</small></span></Link><button className="menu-toggle" onClick={() => setOpen(!open)} aria-label="打开菜单">{open ? <X /> : <Menu />}</button><nav className={`nav-links ${open ? 'nav-open' : ''}`}>{links.map(([label, href]) => <Link className={location.pathname === href ? 'active' : ''} onClick={() => setOpen(false)} key={href} to={href}>{label}</Link>)}<Link className="login-link" to="/login">登录</Link><ActionButton className="nav-cta" onClick={() => window.location.assign('/dashboard')}>开始使用 <span>↗</span></ActionButton></nav></header>; }
