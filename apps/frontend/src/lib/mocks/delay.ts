/** Artificial latency so mock fetchers behave like network calls. */
export function delay(ms = 250): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}
