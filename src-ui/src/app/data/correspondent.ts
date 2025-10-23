import { MatchingModel } from './matching-model'

export interface Correspondent extends MatchingModel {
  last_correspondence?: string // Date
  external_reference?: string
}
