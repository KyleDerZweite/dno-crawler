import * as React from "react"
import { Tooltip } from "@base-ui/react"

import { cn } from "@/lib/utils"

const TooltipProvider = ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
)

const TooltipRoot = Tooltip.Root

interface TooltipTriggerProps extends Omit<React.ComponentPropsWithoutRef<typeof Tooltip.Trigger>, 'render'> {
    asChild?: boolean
}

const TooltipTrigger = React.forwardRef<HTMLButtonElement, TooltipTriggerProps>(
    ({ asChild, children, ...props }, ref) => {
        if (asChild && React.isValidElement(children)) {
            return (
                <Tooltip.Trigger ref={ref} render={children} {...props} />
            )
        }
        return (
            <Tooltip.Trigger ref={ref} {...props}>
                {children}
            </Tooltip.Trigger>
        )
    }
)
TooltipTrigger.displayName = "TooltipTrigger"

const TooltipContent = React.forwardRef<
    HTMLDivElement,
    React.ComponentPropsWithoutRef<typeof Tooltip.Popup>
>(({ className, children, ...props }, ref) => (
    <Tooltip.Portal>
        <Tooltip.Positioner>
            <Tooltip.Popup
                ref={ref}
                className={cn(
                    "z-50 overflow-hidden rounded-md bg-primary px-3 py-1.5 text-xs text-primary-foreground animate-in fade-in-0 zoom-in-95 data-[closed]:animate-out data-[closed]:fade-out-0 data-[closed]:zoom-out-95",
                    className
                )}
                {...props}
            >
                {children}
                <Tooltip.Arrow className="fill-primary" />
            </Tooltip.Popup>
        </Tooltip.Positioner>
    </Tooltip.Portal>
))
TooltipContent.displayName = "TooltipContent"

export {
    TooltipProvider,
    TooltipRoot as Tooltip,
    TooltipTrigger,
    TooltipContent,
}
