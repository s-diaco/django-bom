import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { fetchPartBom, fetchPartDetail } from '../api/endpoints'
import type { PartBomResponse, PartDetail } from '../types'

function normalizeIndentLevel(level: number | null): number {
  return Math.max(level ?? 0, 0)
}

function hasNextAtLevel(items: PartBomResponse['items'], startIndex: number, targetLevel: number): boolean {
  for (let index = startIndex + 1; index < items.length; index += 1) {
    const currentLevel = normalizeIndentLevel(items[index].indent_level)
    if (currentLevel < targetLevel) {
      return false
    }
    if (currentLevel === targetLevel) {
      return true
    }
  }
  return false
}

export function PartDetailPage() {
  const { partId } = useParams()

  const [detail, setDetail] = useState<PartDetail | null>(null)
  const [bom, setBom] = useState<PartBomResponse | null>(null)
  const [viewMode, setViewMode] = useState<'indented' | 'flat'>('indented')
  const [quantityInput, setQuantityInput] = useState('100')

  const [loadingDetail, setLoadingDetail] = useState(false)
  const [loadingBom, setLoadingBom] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')

  const isIndentedView = viewMode === 'indented'

  useEffect(() => {
    if (!partId) {
      return
    }
    const stablePartId = partId

    let cancelled = false
    async function loadDetail() {
      setLoadingDetail(true)
      setErrorMessage('')

      try {
        const response = await fetchPartDetail(stablePartId)
        if (!cancelled) {
          setDetail(response)
        }
      } catch {
        if (!cancelled) {
          setErrorMessage('Unable to load part detail.')
        }
      } finally {
        if (!cancelled) {
          setLoadingDetail(false)
        }
      }
    }

    void loadDetail()
    return () => {
      cancelled = true
    }
  }, [partId])

  useEffect(() => {
    if (!partId) {
      return
    }
    const stablePartId = partId

    const quantity = Number.parseInt(quantityInput, 10)
    if (!Number.isInteger(quantity) || quantity < 1) {
      setBom(null)
      return
    }

    let cancelled = false
    async function loadBom() {
      setLoadingBom(true)
      setErrorMessage('')

      try {
        const response = await fetchPartBom({ partId: stablePartId, quantity, view: viewMode })
        if (!cancelled) {
          setBom(response)
        }
      } catch {
        if (!cancelled) {
          setErrorMessage('Unable to load BOM data for this part.')
        }
      } finally {
        if (!cancelled) {
          setLoadingBom(false)
        }
      }
    }

    void loadBom()
    return () => {
      cancelled = true
    }
  }, [partId, quantityInput, viewMode])

  return (
    <main className="shell">
      <section className="panel">
        <header className="topbar">
          <div>
            <p className="eyebrow">Part Detail</p>
            <h1>{detail?.part_number || 'Loading...'}</h1>
            <p className="muted">
              {detail?.part_class ? `${detail.part_class.code} - ${detail.part_class.name}` : 'No class'}
              {' • Rev '}
              {detail?.revision || '-'}
            </p>
          </div>
          <Link className="text-link" to="/">
            Back to dashboard
          </Link>
        </header>

        {errorMessage && <p className="error">{errorMessage}</p>}

        {loadingDetail && <p className="status">Loading part detail...</p>}
        {detail && (
          <section className="card-grid">
            <article className="card">
              <h2>Description</h2>
              <p>{detail.description || detail.synopsis || '-'}</p>
            </article>
            <article className="card">
              <h2>Primary Manufacturer</h2>
              <p>
                {detail.primary_manufacturer_name || '-'}
                {detail.primary_manufacturer_part_number
                  ? ` (${detail.primary_manufacturer_part_number})`
                  : ''}
              </p>
            </article>
          </section>
        )}

        <section className="bom-controls">
          <label>
            View
            <select value={viewMode} onChange={(event) => setViewMode(event.target.value as 'indented' | 'flat')}>
              <option value="indented">Indented</option>
              <option value="flat">Flat</option>
            </select>
          </label>

          <label>
            Quantity
            <input
              type="number"
              min={1}
              value={quantityInput}
              onChange={(event) => setQuantityInput(event.target.value)}
            />
          </label>
        </section>

        {loadingBom && <p className="status">Loading BOM...</p>}

        {bom && (
          <>
            <section className="card-grid">
              <article className="card">
                <h2>Unit Cost</h2>
                <p>{bom.summary.unit_cost}</p>
              </article>
              <article className="card">
                <h2>Out Of Pocket</h2>
                <p>{bom.summary.out_of_pocket_cost}</p>
              </article>
              <article className="card">
                <h2>Missing Costs</h2>
                <p>{bom.summary.missing_item_costs}</p>
              </article>
            </section>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Part</th>
                    <th>Rev</th>
                    {!isIndentedView && <th>Indent</th>}
                    <th>Qty</th>
                    <th>Total Qty</th>
                    <th>Refs</th>
                    <th>Seller</th>
                  </tr>
                </thead>
                <tbody>
                  {bom.items.length === 0 && (
                    <tr>
                      <td className="status" colSpan={isIndentedView ? 6 : 7}>
                        No BOM items found.
                      </td>
                    </tr>
                  )}
                  {bom.items.map((item, rowIndex) => {
                    const itemLevel = normalizeIndentLevel(item.indent_level)
                    const hasSiblingAtSameLevel = hasNextAtLevel(bom.items, rowIndex, itemLevel)
                    const branchPrefix = Array.from({ length: itemLevel }, (_, depth) => (
                      <span
                        key={`depth-${depth}`}
                        className={hasNextAtLevel(bom.items, rowIndex, depth) ? 'tree-guide tree-guide-line' : 'tree-guide'}
                      >
                        │
                      </span>
                    ))

                    return (
                    <tr key={item.bom_id}>
                      <td>
                        <div className={isIndentedView ? 'tree-cell' : undefined}>
                          {isIndentedView && (
                            <span className="tree-prefix" aria-hidden="true">
                              {branchPrefix}
                              <span className="tree-guide tree-guide-branch">{hasSiblingAtSameLevel ? '├' : '└'}</span>
                              <span className="tree-guide tree-guide-branch">─</span>
                            </span>
                          )}
                          <span className={isIndentedView ? 'tree-part' : undefined}>{item.part_number}</span>
                        </div>
                      </td>
                      <td>{item.revision}</td>
                      {!isIndentedView && <td>{item.indent_level ?? '-'}</td>}
                      <td>{item.extended_quantity}</td>
                      <td>{item.total_extended_quantity}</td>
                      <td>{item.references || '-'}</td>
                      <td>
                        {item.seller.name || '-'}
                        {item.seller.seller_part_number ? ` (${item.seller.seller_part_number})` : ''}
                      </td>
                    </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </main>
  )
}