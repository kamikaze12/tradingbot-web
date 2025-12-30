import React from 'react';
import { Activity, Clock, AlertCircle, CheckCircle } from 'lucide-react';

interface ScrapingJob {
  id: string;
  source: string;
  status: 'running' | 'completed' | 'failed' | 'queued';
  progress: number;
  startTime: string;
  duration: string;
  recordsCollected: number;
  lastError?: string;
}

interface ScrapingStatusProps {
  jobs: ScrapingJob[];
  isDarkMode: boolean;
}

export const ScrapingStatus: React.FC<ScrapingStatusProps> = ({ jobs, isDarkMode }) => {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return <Activity className="w-4 h-4 text-blue-500 animate-pulse" />;
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      case 'queued':
        return <Clock className="w-4 h-4 text-yellow-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return isDarkMode ? 'bg-blue-900 text-blue-300' : 'bg-blue-100 text-blue-800';
      case 'completed':
        return isDarkMode ? 'bg-green-900 text-green-300' : 'bg-green-100 text-green-800';
      case 'failed':
        return isDarkMode ? 'bg-red-900 text-red-300' : 'bg-red-100 text-red-800';
      case 'queued':
        return isDarkMode ? 'bg-yellow-900 text-yellow-300' : 'bg-yellow-100 text-yellow-800';
      default:
        return isDarkMode ? 'bg-gray-700 text-gray-300' : 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className={`rounded-xl border ${
      isDarkMode 
        ? 'bg-gray-800 border-gray-700' 
        : 'bg-white border-gray-200'
    }`}>
      <div className="p-6 border-b border-gray-200 dark:border-gray-700">
        <h2 className={`text-xl font-semibold ${
          isDarkMode ? 'text-white' : 'text-gray-900'
        }`}>
          Scraping Status
        </h2>
      </div>

      <div className="p-6">
        <div className="space-y-4">
          {jobs.map((job) => (
            <div
              key={job.id}
              className={`p-4 rounded-lg border ${
                isDarkMode 
                  ? 'bg-gray-700 border-gray-600' 
                  : 'bg-gray-50 border-gray-200'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-3">
                  {getStatusIcon(job.status)}
                  <div>
                    <h3 className={`font-medium ${
                      isDarkMode ? 'text-white' : 'text-gray-900'
                    }`}>
                      {job.source}
                    </h3>
                    <p className={`text-sm ${
                      isDarkMode ? 'text-gray-400' : 'text-gray-600'
                    }`}>
                      Started: {job.startTime}
                    </p>
                  </div>
                </div>
                
                <div className="flex items-center space-x-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    getStatusColor(job.status)
                  }`}>
                    {job.status}
                  </span>
                  <span className={`text-sm ${
                    isDarkMode ? 'text-gray-400' : 'text-gray-600'
                  }`}>
                    {job.duration}
                  </span>
                </div>
              </div>

              {job.status === 'running' && (
                <div className="mb-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-sm ${
                      isDarkMode ? 'text-gray-300' : 'text-gray-700'
                    }`}>
                      Progress
                    </span>
                    <span className={`text-sm font-medium ${
                      isDarkMode ? 'text-gray-300' : 'text-gray-700'
                    }`}>
                      {job.progress}%
                    </span>
                  </div>
                  <div className={`w-full bg-gray-200 rounded-full h-2 ${
                    isDarkMode ? 'bg-gray-600' : 'bg-gray-200'
                  }`}>
                    <div
                      className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${job.progress}%` }}
                    />
                  </div>
                </div>
              )}

              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <span className={`text-sm ${
                    isDarkMode ? 'text-gray-300' : 'text-gray-700'
                  }`}>
                    Records: <span className="font-medium">{job.recordsCollected.toLocaleString()}</span>
                  </span>
                </div>
                
                {job.lastError && (
                  <span className="text-sm text-red-500 truncate max-w-xs">
                    {job.lastError}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};