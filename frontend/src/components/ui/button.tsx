import * as React from "react"

const buttonVariants = {
  default: "bg-slate-900 text-slate-50 hover:bg-slate-800 dark:bg-slate-50 dark:text-slate-900 dark:hover:bg-slate-200",
  outline: "border border-slate-200 bg-white hover:bg-slate-100 dark:border-slate-800 dark:bg-slate-950 dark:hover:bg-slate-800",
}

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof buttonVariants
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", ...props }, ref) => (
    <button
      className={`inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-950 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 dark:ring-offset-slate-950 dark:focus-visible:ring-slate-300 h-10 px-4 py-2 ${buttonVariants[variant]} ${className}`}
      ref={ref}
      {...props}
    />
  )
)
Button.displayName = "Button"

export { Button }
