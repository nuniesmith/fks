// components/FileSection.tsx
import { FileText } from 'lucide-react';
import React from 'react';

interface FileItem {
  name: string;
  description: string;
  template: string;
}

interface FileSectionProps {
  title: string;
  icon: React.ComponentType<any>;
  files: FileItem[];
  folderPath: string;
  folderColor: string;
  onGenerateTemplate: (template: string, fileName: string) => void;
}

export const FileSection: React.FC<FileSectionProps> = ({
  title,
  icon: Icon,
  files,
  folderPath,
  folderColor,
  onGenerateTemplate
}) => (
  <div className="bg-white rounded-lg border border-gray-200 p-4">
    <div className="flex items-center mb-3">
      <Icon className={`w-5 h-5 mr-2`} />
      <h3 className="text-lg font-semibold">{title} ({files.length} files)</h3>
    </div>
    <div className="grid gap-2">
      {files.map((file, idx) => (
        <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded border">
          <div className="flex items-center">
            <FileText className="w-4 h-4 text-gray-500 mr-2" />
            <div>
              <span className="font-medium">{file.name}</span>
              <p className="text-sm text-gray-600">{file.description}</p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <span className={`px-2 py-1 bg-${folderColor}-100 text-${folderColor}-800 text-xs rounded`}>
              {folderPath}
            </span>
            <button
              className="px-3 py-1 bg-blue-500 text-white text-xs rounded hover:bg-blue-600"
              onClick={() => onGenerateTemplate(file.template, file.name)}
            >
              Template
            </button>
          </div>
        </div>
      ))}
    </div>
  </div>
);