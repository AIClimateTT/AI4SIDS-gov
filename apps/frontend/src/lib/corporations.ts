/** Canonical corporation ids stored in the database (Survey123 Municipal Boundary). */
export const CANONICAL_CORPORATIONS = [
  'san_juan_laventille_regional_co',
  'tunapuna_piarco_regional_corpor',
  'sangre_grande_regional_corporat',
  'penal_debe_regional_corporation',
  'couva_tabaquite_talparo_regiona',
  'mayaro_rio_claro_regional_corpo',
  'siparia_regional_corporation',
  'princes_town_regional_corporati',
  'diego_martin_regional_corporati',
  'san_fernando_city_corporation',
  'chaguanas_borough_corporation',
  'port_of_spain_city_corporation',
  'point_fortin_borough_corporatio',
  'arima_borough_corporation',
] as const

export type CanonicalCorporation = (typeof CANONICAL_CORPORATIONS)[number]

/**
 * Whether a value is one of the fourteen.
 *
 * Lives here rather than beside each caller because a slug outside this set is
 * never merely "not found": it matches no rows, so every count comes back zero
 * and the screen reads as an authoritative "nothing happened" for a region that
 * may have filed plenty. `POST /reports` rejects unknown corporations
 * server-side for exactly this reason; routes that take a corporation in the
 * URL need the same guard before they render anything.
 */
export function isCanonicalCorporation(
  value: unknown,
): value is CanonicalCorporation {
  return (
    typeof value === 'string' &&
    (CANONICAL_CORPORATIONS as readonly string[]).includes(value)
  )
}

export type CorporationOption = {
  value: CanonicalCorporation
  label: string
}

/**
 * Proper names for display. The canonical ids are truncated to 31 characters by
 * the Survey123 export, so deriving a label from the id yields "Diego Martin
 * Regional Corporati". These strings are the only thing a user should ever see.
 */
export const CORPORATION_LABELS: Record<CanonicalCorporation, string> = {
  san_juan_laventille_regional_co: 'San Juan/Laventille Regional Corporation',
  tunapuna_piarco_regional_corpor: 'Tunapuna/Piarco Regional Corporation',
  sangre_grande_regional_corporat: 'Sangre Grande Regional Corporation',
  penal_debe_regional_corporation: 'Penal/Debe Regional Corporation',
  couva_tabaquite_talparo_regiona:
    'Couva/Tabaquite/Talparo Regional Corporation',
  mayaro_rio_claro_regional_corpo: 'Mayaro/Rio Claro Regional Corporation',
  siparia_regional_corporation: 'Siparia Regional Corporation',
  princes_town_regional_corporati: 'Princes Town Regional Corporation',
  diego_martin_regional_corporati: 'Diego Martin Regional Corporation',
  san_fernando_city_corporation: 'San Fernando City Corporation',
  chaguanas_borough_corporation: 'Chaguanas Borough Corporation',
  port_of_spain_city_corporation: 'Port of Spain City Corporation',
  point_fortin_borough_corporatio: 'Point Fortin Borough Corporation',
  arima_borough_corporation: 'Arima Borough Corporation',
}

export const CORPORATION_OPTIONS: CorporationOption[] =
  CANONICAL_CORPORATIONS.map((value) => ({
    value,
    label: CORPORATION_LABELS[value],
  })).sort((a, b) => a.label.localeCompare(b.label))
