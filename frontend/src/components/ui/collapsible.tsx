import * as React from "react"
import { Collapsible as BaseCollapsible } from "@base-ui/react"

const Collapsible = BaseCollapsible.Root

const CollapsibleTrigger = BaseCollapsible.Trigger

const CollapsibleContent = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof BaseCollapsible.Panel>
>(({ className, ...props }, ref) => (
  <BaseCollapsible.Panel
    ref={ref}
    className={className}
    {...props}
  />
))
CollapsibleContent.displayName = "CollapsibleContent"

export { Collapsible, CollapsibleTrigger, CollapsibleContent }
