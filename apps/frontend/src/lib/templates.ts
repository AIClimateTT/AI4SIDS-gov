export function dropBlankParams(
  params: Record<string, string>,
): Record<string, string> {
  return Object.fromEntries(
    Object.entries(params)
      .map(([name, value]) => [name, value.trim()] as const)
      .filter(([, trimmed]) => trimmed !== ''),
  )
}
