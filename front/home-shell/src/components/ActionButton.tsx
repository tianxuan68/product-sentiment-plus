import { motion } from 'framer-motion';
import type { ButtonHTMLAttributes, ReactNode } from 'react';
type Props = Pick<ButtonHTMLAttributes<HTMLButtonElement>, 'className' | 'disabled' | 'onClick' | 'type' | 'aria-label'> & { children: ReactNode; variant?: 'primary' | 'secondary' | 'ghost' };
export function ActionButton({ children, variant = 'primary', className = '', ...props }: Props) { return <motion.button whileHover={{ y: -2, scale: 1.015 }} whileTap={{ scale: 0.98 }} className={`action-button action-${variant} ${className}`} {...props}>{children}</motion.button>; }
