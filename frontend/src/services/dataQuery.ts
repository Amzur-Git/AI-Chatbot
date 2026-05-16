import axios from "axios";
import type { DataQueryAskResponse, DataQueryDatasetResponse } from "../types";

const dataQueryApi = axios.create({
  baseURL: import.meta.env.VITE_DATA_QUERY_API_URL || "http://localhost:8001",
  timeout: 300000,
});

dataQueryApi.interceptors.request.use((config) => {
  const apiKey = import.meta.env.VITE_DATA_QUERY_API_KEY;
  if (apiKey) {
    config.headers["X-API-Key"] = apiKey;
  }
  return config;
});

export const dataQueryService = {
  async uploadFile(file: File, sessionId?: string): Promise<DataQueryDatasetResponse> {
    const formData = new FormData();
    formData.append("file", file);
    if (sessionId) {
      formData.append("session_id", sessionId);
    }

    const response = await dataQueryApi.post("/upload-file", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      timeout: 240000,
    });
    return response.data;
  },

  async loadGoogleSheet(
    googleSheetUrl: string,
    sessionId?: string,
    worksheetName?: string
  ): Promise<DataQueryDatasetResponse> {
    const response = await dataQueryApi.post("/load-google-sheet", {
      google_sheet_url: googleSheetUrl,
      session_id: sessionId,
      worksheet_name: worksheetName,
    }, {
      timeout: 240000,
    });
    return response.data;
  },

  async askQuestion(params: {
    sessionId: string;
    datasetId?: string;
    sheetName?: string;
    question: string;
    includePandasCode?: boolean;
  }): Promise<DataQueryAskResponse> {
    const response = await dataQueryApi.post("/ask", {
      session_id: params.sessionId,
      dataset_id: params.datasetId,
      sheet_name: params.sheetName,
      question: params.question,
      include_pandas_code: params.includePandasCode ?? true,
    }, {
      timeout: 300000,
    });
    return response.data;
  },
};
