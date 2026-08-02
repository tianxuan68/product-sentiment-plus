type Props = { label?: string; className?: string };
export function ImagePlaceholder({ label = 'Visual asset placeholder', className = '' }: Props) { return <div aria-label={label} className={`image-placeholder ${className}`}><span>{label}</span></div>; }
