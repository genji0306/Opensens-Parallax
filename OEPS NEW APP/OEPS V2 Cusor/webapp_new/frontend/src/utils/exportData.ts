import { Measurement } from '../types';

interface ExportOptions {
  format: 'csv' | 'json' | 'excel';
  includeMetadata?: boolean;
  filename?: string;
}

const formatDate = (date: string) => {
  return new Date(date).toLocaleString();
};

const generateCSV = (data: Measurement[], includeMetadata: boolean): string => {
  const headers = ['Time', 'Value', 'Type'];
  const rows = data.map(d => [
    formatDate(d.time),
    d.value.toString(),
    d.type
  ]);

  const csvContent = [
    headers.join(','),
    ...rows.map(row => row.join(','))
  ].join('\n');

  return csvContent;
};

const generateJSON = (data: Measurement[], includeMetadata: boolean): string => {
  const exportData = {
    metadata: includeMetadata ? {
      exportDate: new Date().toISOString(),
      totalPoints: data.length,
      measurementTypes: [...new Set(data.map(d => d.type))]
    } : undefined,
    data: data.map(d => ({
      time: formatDate(d.time),
      value: d.value,
      type: d.type
    }))
  };

  return JSON.stringify(exportData, null, 2);
};

const generateExcel = async (data: Measurement[], includeMetadata: boolean): Promise<Blob> => {
  // Note: This is a placeholder for Excel export functionality
  // You would need to add a library like xlsx or exceljs to implement this
  throw new Error('Excel export not implemented');
};

export const exportData = async (data: Measurement[], options: ExportOptions): Promise<void> => {
  const {
    format = 'csv',
    includeMetadata = false,
    filename = `measurement_data_${new Date().toISOString()}`
  } = options;

  let content: string | Blob;
  let mimeType: string;

  switch (format) {
    case 'csv':
      content = generateCSV(data, includeMetadata);
      mimeType = 'text/csv';
      break;
    case 'json':
      content = generateJSON(data, includeMetadata);
      mimeType = 'application/json';
      break;
    case 'excel':
      content = await generateExcel(data, includeMetadata);
      mimeType = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
      break;
    default:
      throw new Error(`Unsupported export format: ${format}`);
  }

  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${filename}.${format}`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}; 