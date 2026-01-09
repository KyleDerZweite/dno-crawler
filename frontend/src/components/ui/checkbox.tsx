import * as React from "react"
import { Checkbox as BaseCheckbox } from "@base-ui/react"
import { Check } from "lucide-react"

import { cn } from "@/lib/utils"

interface CheckboxProps extends Omit<React.ComponentPropsWithoutRef<typeof BaseCheckbox.Root>, 'onCheckedChange'> {
  checked?: boolean
  onCheckedChange?: (checked: boolean) => void
}

const Checkbox = React.forwardRef<HTMLButtonElement, CheckboxProps>(
  ({ className, checked, onCheckedChange, ...props }, ref) => (
    <BaseCheckbox.Root
      ref={ref}
      checked={checked}
      onCheckedChange={(checked) => onCheckedChange?.(checked)}
      className={cn(
        "peer h-4 w-4 shrink-0 rounded-sm border border-primary ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[checked]:bg-primary data-[checked]:text-primary-foreground flex items-center justify-center",
        className
      )}
      {...props}
    >
      <BaseCheckbox.Indicator className="flex items-center justify-center text-current">
        <Check className="h-3 w-3" />
      </BaseCheckbox.Indicator>
    </BaseCheckbox.Root>
  )
)
Checkbox.displayName = "Checkbox"

export { Checkbox }
