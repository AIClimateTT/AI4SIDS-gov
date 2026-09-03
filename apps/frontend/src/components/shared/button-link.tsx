import { createLink } from '@tanstack/react-router'
import type { ComponentProps } from 'react'
import type { VariantProps } from 'class-variance-authority'

import { buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type ButtonAnchorProps = ComponentProps<'a'> &
  VariantProps<typeof buttonVariants>

/**
 * A navigation link wearing a button's clothes.
 *
 * The obvious spelling, `<Button render={<Link />}>`, sends an anchor through
 * Base UI's button primitive, which warns in the console. Silencing that with
 * `nativeButton={false}` is worse than the warning: it stamps `role="button"`
 * onto the `<a>` (see useButton's props merge), so a screen reader announces
 * "button" for something that still navigates, still opens in a new tab on
 * ctrl-click, and still offers "copy link address".
 *
 * These controls are links. Only their appearance is a button's, so they take
 * the button's classes and none of its behaviour. `createLink` keeps the
 * router's typed `to` and `params` inference intact through the wrapper.
 */
function ButtonAnchor({
  className,
  variant,
  size,
  ...props
}: ButtonAnchorProps) {
  return (
    <a
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export const ButtonLink = createLink(ButtonAnchor)
