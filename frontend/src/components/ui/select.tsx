import * as React from "react"
import { Select } from "@base-ui/react"
import { Check, ChevronDown, ChevronUp } from "lucide-react"

import { cn } from "@/lib/utils"

// Select Root with backward-compatible API
interface SelectRootProps {
  value?: string
  defaultValue?: string
  onValueChange?: (value: string) => void
  open?: boolean
  onOpenChange?: (open: boolean) => void
  disabled?: boolean
  children?: React.ReactNode
}

const SelectRoot = ({ value, defaultValue, onValueChange, children, ...props }: SelectRootProps) => {
  // Wrap onValueChange to match Radix's simpler signature
  const handleValueChange = React.useCallback((newValue: string | null) => {
    if (onValueChange && newValue !== null) {
      onValueChange(newValue)
    }
  }, [onValueChange])

  return (
    <Select.Root
      value={value}
      defaultValue={defaultValue}
      onValueChange={handleValueChange}
      {...props}
    >
      {children}
    </Select.Root>
  )
}

const SelectGroup = Select.Group

// SelectValue with placeholder support
interface SelectValueProps extends React.ComponentPropsWithoutRef<typeof Select.Value> {
  placeholder?: string
}

const SelectValue = React.forwardRef<HTMLSpanElement, SelectValueProps>(
  ({ placeholder, children, ...props }, ref) => (
    <Select.Value ref={ref} {...props}>
      {(value) => value ?? (placeholder ? <span className="text-muted-foreground">{placeholder}</span> : null)}
    </Select.Value>
  )
)
SelectValue.displayName = "SelectValue"

const SelectTrigger = React.forwardRef<
  HTMLButtonElement,
  React.ComponentPropsWithoutRef<typeof Select.Trigger>
>(({ className, children, ...props }, ref) => (
  <Select.Trigger
    ref={ref}
    className={cn(
      "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50 [&>span]:line-clamp-1",
      className
    )}
    {...props}
  >
    {children}
    <Select.Icon>
      <ChevronDown className="h-4 w-4 opacity-50" />
    </Select.Icon>
  </Select.Trigger>
))
SelectTrigger.displayName = "SelectTrigger"

const SelectScrollUpButton = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof Select.ScrollUpArrow>
>(({ className, ...props }, ref) => (
  <Select.ScrollUpArrow
    ref={ref}
    className={cn(
      "flex cursor-default items-center justify-center py-1",
      className
    )}
    {...props}
  >
    <ChevronUp className="h-4 w-4" />
  </Select.ScrollUpArrow>
))
SelectScrollUpButton.displayName = "SelectScrollUpButton"

const SelectScrollDownButton = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof Select.ScrollDownArrow>
>(({ className, ...props }, ref) => (
  <Select.ScrollDownArrow
    ref={ref}
    className={cn(
      "flex cursor-default items-center justify-center py-1",
      className
    )}
    {...props}
  >
    <ChevronDown className="h-4 w-4" />
  </Select.ScrollDownArrow>
))
SelectScrollDownButton.displayName = "SelectScrollDownButton"

interface SelectContentProps extends React.ComponentPropsWithoutRef<typeof Select.Popup> {
  position?: "popper" | "item-aligned"
}

const SelectContent = React.forwardRef<
  HTMLDivElement,
  SelectContentProps
>(({ className, children, position = "popper", ...props }, ref) => (
  <Select.Portal>
    <Select.Positioner
      side="bottom"
      sideOffset={position === "popper" ? 4 : 0}
    >
      <Select.Popup
        ref={ref}
        className={cn(
          "relative z-50 max-h-96 min-w-[8rem] overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md data-[open]:animate-in data-[closed]:animate-out data-[closed]:fade-out-0 data-[open]:fade-in-0 data-[closed]:zoom-out-95 data-[open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
          position === "popper" &&
          "data-[side=bottom]:translate-y-1 data-[side=left]:-translate-x-1 data-[side=right]:translate-x-1 data-[side=top]:-translate-y-1",
          className
        )}
        {...props}
      >
        <SelectScrollUpButton />
        <Select.List className="p-1">
          {children}
        </Select.List>
        <SelectScrollDownButton />
      </Select.Popup>
    </Select.Positioner>
  </Select.Portal>
))
SelectContent.displayName = "SelectContent"

const SelectLabel = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof Select.GroupLabel>
>(({ className, ...props }, ref) => (
  <Select.GroupLabel
    ref={ref}
    className={cn("py-1.5 pl-8 pr-2 text-sm font-semibold", className)}
    {...props}
  />
))
SelectLabel.displayName = "SelectLabel"

// SelectItem with string value support for backward compatibility
interface SelectItemProps extends Omit<React.ComponentPropsWithoutRef<typeof Select.Item>, 'value'> {
  value: string
}

const SelectItem = React.forwardRef<HTMLDivElement, SelectItemProps>(
  ({ className, children, value, ...props }, ref) => (
    <Select.Item
      ref={ref}
      value={value}
      className={cn(
        "relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
        className
      )}
      {...props}
    >
      <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
        <Select.ItemIndicator>
          <Check className="h-4 w-4" />
        </Select.ItemIndicator>
      </span>

      <Select.ItemText>{children}</Select.ItemText>
    </Select.Item>
  )
)
SelectItem.displayName = "SelectItem"

const SelectSeparator = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof Select.Separator>
>(({ className, ...props }, ref) => (
  <Select.Separator
    ref={ref}
    className={cn("-mx-1 my-1 h-px bg-muted", className)}
    {...props}
  />
))
SelectSeparator.displayName = "SelectSeparator"

export {
  SelectRoot as Select,
  SelectGroup,
  SelectValue,
  SelectTrigger,
  SelectContent,
  SelectLabel,
  SelectItem,
  SelectSeparator,
  SelectScrollUpButton,
  SelectScrollDownButton,
}
