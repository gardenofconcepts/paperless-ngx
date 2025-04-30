import { MatchingModel } from './matching-model'

export interface Correspondent extends MatchingModel {
  external_reference?: string
  last_correspondence?: string // Date
}
