/**
 * Turn a snake_case constant into a human-readable Title Case label.
 *
 * @example formatConstant("this_is_a_constant") // "This Is A Constant"
 */
export function formatConstant(value: string): string {
  return value
    .split('_')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ')
}
