export interface OrganizationSummary {
  id: number
  name: string
  subscription: string
  currency: string
  number_scheme: string
}

export interface UserProfile {
  role: string
  role_display: string
  organization: OrganizationSummary | null
  is_google_authenticated: boolean
}

export interface MeResponse {
  id: number
  username: string
  first_name: string
  last_name: string
  email: string
  is_active: boolean
  profile: UserProfile | null
}

export interface PartClassSummary {
  id: number
  code: string
  name: string
}

export interface PartListRow {
  id: number
  part_id: number
  part_number: string
  part_class: PartClassSummary | null
  revision: string
  description: string
  synopsis: string
  material: string | null
  primary_manufacturer_name: string
  primary_manufacturer_part_number: string
}

export interface PartDetail {
  id: number
  part_id: number
  part_number: string
  part_class: PartClassSummary | null
  revision: string
  timestamp: string
  configuration: string
  description: string
  synopsis: string
  material: string | null
  primary_manufacturer_name: string
  primary_manufacturer_part_number: string
}

export interface BomSeller {
  id: number | null
  name: string
  seller_part_number: string
}

export interface BomItem {
  bom_id: string
  parent_id: string | null
  indent_level: number | null
  part_id: number
  part_revision_id: number
  part_number: string
  revision: string
  description: string
  references: string
  quantity: number
  extended_quantity: number
  total_extended_quantity: number
  do_not_load: boolean
  seller: BomSeller
}

export interface PartBomSummary {
  unit_cost: string
  missing_item_costs: number
  nre_cost: string
  out_of_pocket_cost: string
}

export interface PartBomResponse {
  part_id: number
  part_revision_id: number
  part_number: string
  view: 'indented' | 'flat'
  quantity: number
  summary: PartBomSummary
  items: BomItem[]
}

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}