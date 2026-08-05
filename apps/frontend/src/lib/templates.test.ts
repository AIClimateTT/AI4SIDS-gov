import { describe, expect, it } from 'vitest'

import { dropBlankParams } from '@/lib/templates'

describe('dropBlankParams', () => {
  it('drops a param the officer left blank', () => {
    // The generate form seeds every template param to '', including optional
    // ones. Posting community: '' made the backend filter on the empty string
    // and report zero incidents for a region that had three.
    expect(
      dropBlankParams({
        corporation: 'arima_borough_corporation',
        community: '',
        date_from: '2024-06-01',
        date_to: '2024-06-30',
      }),
    ).toEqual({
      corporation: 'arima_borough_corporation',
      date_from: '2024-06-01',
      date_to: '2024-06-30',
    })
  })

  it('drops a param containing only whitespace', () => {
    expect(dropBlankParams({ community: '   ' })).toEqual({})
  })

  it('trims the values it keeps', () => {
    expect(dropBlankParams({ community: '  Arima  ' })).toEqual({
      community: 'Arima',
    })
  })

  it('leaves a fully populated param set untouched', () => {
    const params = { corporation: 'arima_borough_corporation', community: 'Arima' }

    expect(dropBlankParams(params)).toEqual(params)
  })
})
