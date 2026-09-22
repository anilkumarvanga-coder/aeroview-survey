/** Data contracts only. Service credentials must never be included in browser code. */
export type SurveyJobStatus = 'uploading' | 'queued' | 'processing' | 'completed' | 'partial' | 'failed';
export interface SurveyProject { id: string; name: string; created_at: string }
export interface SurveyJob { id: string; project_id: string; status: SurveyJobStatus; progress: number; error: string | null; created_at: string; updated_at: string }
export interface SurveyLayer {
  id: string; projectId: string; jobId: string; name: string; sourcePath: string;
  kind: 'orthomosaic' | 'dsm' | 'dtm' | 'pointcloud' | 'unknown';
  status: 'ready' | 'failed'; error: string | null;
  tileUrl: string | null; downloadUrl: string | null; previewUrl: string | null;
  crs?: string; bounds?: [number, number, number, number];
  resolution?: [number, number]; elevationUnit?: string | null;
  width?: number; height?: number; bands?: number; dataType?: string;
  displayRange?: [number, number]; displayRangeMethod?: string;
  sourcePointCount?: number; previewPointCount?: number;
  boundsNative?: [number, number, number, number, number, number]; previewOnly?: boolean;
}
export interface SurveyDashboard {
  project: SurveyProject; projectType: 'land-survey'; layers: SurveyLayer[]; jobs: SurveyJob[];
  summary: { readyLayers: number; failedLayers: number };
  observations: never[]; observationsMessage: string; liveStream: null; recordings: never[];
}
export interface PointPreview { crs: string; origin: [number,number,number]; positions: [number,number,number][]; sourcePointCount: number; sampled: boolean }
