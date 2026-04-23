import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchPartBom, fetchPartDetail } from '../api/endpoints'
import { PartDetailPage } from './PartDetailPage'

vi.mock('../api/endpoints', () => ({
  fetchPartDetail: vi.fn(),
  fetchPartBom: vi.fn(),
}))

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/parts/42']}>
      <Routes>
        <Route path="/parts/:partId" element={<PartDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

const detailFixture = {
  id: 501,
  part_id: 42,
  part_number: 'PN-0042',
  part_class: { id: 1, code: 'ASM', name: 'Assembly' },
  revision: 'A',
  timestamp: '2026-01-01T00:00:00Z',
  configuration: '',
  description: 'Top-level assembly',
  synopsis: '',
  material: null,
  primary_manufacturer_name: 'Acme',
  primary_manufacturer_part_number: 'AC-42',
}

const bomFixture = {
  part_id: 42,
  part_revision_id: 501,
  part_number: 'PN-0042',
  view: 'indented' as const,
  quantity: 100,
  summary: {
    unit_cost: '$5.20',
    missing_item_costs: 0,
    nre_cost: '$0.00',
    out_of_pocket_cost: '$520.00',
  },
  items: [
    {
      bom_id: '501',
      parent_id: null,
      indent_level: 0,
      part_id: 42,
      part_revision_id: 501,
      part_number: 'PN-0042',
      revision: 'A',
      description: 'Top-level assembly',
      references: '',
      quantity: 1,
      extended_quantity: 100,
      total_extended_quantity: 100,
      do_not_load: false,
      seller: {
        id: null,
        name: '',
        seller_part_number: '',
      },
    },
    {
      bom_id: '700',
      parent_id: '501',
      indent_level: 1,
      part_id: 77,
      part_revision_id: 700,
      part_number: 'PN-0077',
      revision: 'B',
      description: 'Child component',
      references: 'R1',
      quantity: 2,
      extended_quantity: 200,
      total_extended_quantity: 200,
      do_not_load: false,
      seller: {
        id: null,
        name: 'BestParts',
        seller_part_number: 'BP-77',
      },
    },
  ],
}

describe('PartDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(fetchPartDetail).mockResolvedValue(detailFixture)
    vi.mocked(fetchPartBom).mockResolvedValue(bomFixture)
  })

  it('loads and renders part detail and BOM summary', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { level: 1, name: 'PN-0042' })).toBeInTheDocument()
    expect(await screen.findByText('Top-level assembly')).toBeInTheDocument()
    expect(await screen.findByText('$5.20')).toBeInTheDocument()
    expect(screen.getByText('PN-0077')).toBeInTheDocument()

    expect(fetchPartDetail).toHaveBeenCalledWith('42')
    expect(fetchPartBom).toHaveBeenCalledWith({
      partId: '42',
      quantity: 100,
      view: 'indented',
    })

    expect(screen.queryByRole('columnheader', { name: 'Indent' })).not.toBeInTheDocument()
  })

  it('switches to flat mode and shows indent column', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { level: 1, name: 'PN-0042' })

    await user.selectOptions(screen.getByLabelText('View'), 'flat')

    await waitFor(() => {
      expect(fetchPartBom).toHaveBeenLastCalledWith({
        partId: '42',
        quantity: 100,
        view: 'flat',
      })
    })

    expect(screen.getByRole('columnheader', { name: 'Indent' })).toBeInTheDocument()
  })

  it('shows an error when BOM loading fails', async () => {
    vi.mocked(fetchPartBom).mockRejectedValueOnce(new Error('network error'))
    renderPage()

    expect(await screen.findByText('Unable to load BOM data for this part.')).toBeInTheDocument()
  })
})
