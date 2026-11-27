import { motion } from "framer-motion";

const VARIANT_CLASSES = {
  primary:
    "bg-gradient-to-r from-[#FF6B00] via-[#FF7A1A] to-[#FF9100] text-white shadow-[0_10px_30px_-8px_rgba(255,107,0,0.65)] border border-[#FF9100]/40 hover:brightness-110",
  glass:
    "backdrop-blur-md bg-white/5 hover:bg-white/10 text-white border border-white/15 shadow-lg",
  emerald:
    "bg-[#00E676]/15 hover:bg-[#00E676]/25 text-[#00E676] border border-[#00E676]/35 shadow-[0_8px_24px_-8px_rgba(0,230,118,0.45)]",
  danger:
    "bg-red-500/15 hover:bg-red-500/25 text-red-300 border border-red-500/35",
  ghost:
    "bg-transparent hover:bg-white/5 text-white/70 hover:text-white border border-transparent",
};

const SIZE_CLASSES = {
  sm: "px-3.5 py-2 text-xs rounded-xl",
  md: "px-5 py-2.5 text-sm rounded-2xl",
  lg: "px-6 py-3.5 text-sm rounded-2xl",
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  fullWidth = false,
  className = "",
  disabled = false,
  type = "button",
  onClick,
  ...props
}) {
  return (
    <motion.button
      type={type}
      disabled={disabled}
      onClick={onClick}
      whileHover={disabled ? undefined : { scale: 1.02 }}
      whileTap={disabled ? undefined : { scale: 0.98 }}
      transition={{ type: "spring", stiffness: 420, damping: 26 }}
      className={`inline-flex items-center justify-center gap-2 font-semibold tracking-tight transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${
        VARIANT_CLASSES[variant] || VARIANT_CLASSES.primary
      } ${SIZE_CLASSES[size] || SIZE_CLASSES.md} ${fullWidth ? "w-full" : ""} ${className}`}
      {...props}
    >
      {children}
    </motion.button>
  );
}
