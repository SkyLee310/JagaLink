// Short names for the generated API types (D-42). Run `make types` after every API change.
import type { components } from './schema'

type Schemas = components['schemas']

export type ApiErrorBody = Schemas['ErrorOut']
export type Session = Schemas['SessionOut']
export type SessionUser = Schemas['SessionUserOut']
export type Layout = Schemas['LayoutOut']
export type LayoutZone = Schemas['ZoneOut']
export type LayoutNode = Schemas['NodeOut']
export type LayoutLink = Schemas['LinkOut']
export type LayoutInput = Schemas['LayoutIn']
export type LayoutFile = Schemas['LayoutFile']
