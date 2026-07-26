import { formatConstant } from '@/lib/format-constant'

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

export type CorporationOption = {
  value: CanonicalCorporation
  label: string
}

export const CORPORATION_OPTIONS: CorporationOption[] =
  CANONICAL_CORPORATIONS.map((value) => ({
    value,
    label: formatConstant(value),
  })).sort((a, b) => a.label.localeCompare(b.label))
