import React from 'react';
import { Globe, CheckCircle, AlertCircle, Clock, TrendingUp } from 'lucide-react';

interface DataSource {
  id: string;
  name: string;
  url: string;
  status: 'active' | 'error' | 'pending';
  lastUpdate: string;
  dataPoints: number;
  pairs: string[];
}

interface DataSourceCardProps {
  source: DataSource;
  isDarkMode: boolean;
  onToggle: (id: string) => void;
}

export const DataSourceCard: React.FC<DataSourceCardProps> = ({ 
  source, 
  isDarkMode, 
  onToggle 
}) => {
  const getStatusIcon = () => {
    switch (source.status) {
      case 'active':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'error':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      case 'pending':
        return <Clock className="w-5 h-5 text-yellow-500" />;
    }
  };

  const getStatusColor = () => {
    switch (source.status) {
      case 'active':
        return 'bg-green-100 text-green-800';
      case 'error':
        return 'bg-red-100 text-red-800';
      case 'pending':
        return 'bg-yellow-100 text-yellow-800';
    }
  };

  return (
    <div className={`rounded-xl border transition-all duration-200 hover:shadow-lg ${
      isDarkMode 
        ? 'bg-gray-800 border-gray-700 hover:shadow-gray-900/20' 
        : 'bg-white border-gray-200 hover:shadow-blue-100/50'
    }`}>
      <div className="p-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-lg ${
              isDarkMode ? 'bg-gray-700' : 'bg-gray-100'
            }`}>
              <Globe className={`w-5 h-5 ${
                isDarkMode ? 'text-gray-300' : 'text-gray-600'
              }`} />
            </div>
            <div>
              <h3 className={`font-semibold ${
                isDarkMode ? 'text-white' : 'text-gray-900'
              }`}>
                {source.name}
              </h3>
              <p className={`text-sm ${
                isDarkMode ? 'text-gray-400' : 'text-gray-600'
              }`}>
                {source.url}
              </p>
            </div>
          </div>
          
          <div className="flex items-center space-x-2">
            {getStatusIcon()}
            <span className={`px-2 py-1 rounded-full text-xs font-medium ${
              isDarkMode ? 'bg-gray-700 text-gray-300' : getStatusColor()
            }`}>
              {source.status}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className={`p-3 rounded-lg ${
            isDarkMode ? 'bg-gray-700' : 'bg-gray-50'
          }`}>
            <div className="flex items-center space-x-2">
              <TrendingUp className="w-4 h-4 text-blue-500" />
              <span className={`text-sm font-medium ${
                isDarkMode ? 'text-gray-300' : 'text-gray-700'
              }`}>
                Data Points
              </span>
            </div>
            <p className={`text-lg font-bold ${
              isDarkMode ? 'text-white' : 'text-gray-900'
            }`}>
              {source.dataPoints.toLocaleString()}
            </p>
          </div>
          
          <div className={`p-3 rounded-lg ${
            isDarkMode ? 'bg-gray-700' : 'bg-gray-50'
          }`}>
            <div className="flex items-center space-x-2">
              <Clock className="w-4 h-4 text-green-500" />
              <span className={`text-sm font-medium ${
                isDarkMode ? 'text-gray-300' : 'text-gray-700'
              }`}>
                Last Update
              </span>
            </div>
            <p className={`text-sm ${
              isDarkMode ? 'text-gray-400' : 'text-gray-600'
            }`}>
              {source.lastUpdate}
            </p>
          </div>
        </div>

        <div className="mb-4">
          <p className={`text-sm font-medium mb-2 ${
            isDarkMode ? 'text-gray-300' : 'text-gray-700'
          }`}>
            Currency Pairs ({source.pairs.length})
          </p>
          <div className="flex flex-wrap gap-2">
            {source.pairs.slice(0, 6).map((pair, index) => (
              <span
                key={index}
                className={`px-2 py-1 rounded text-xs font-medium ${
                  isDarkMode 
                    ? 'bg-blue-900 text-blue-300' 
                    : 'bg-blue-100 text-blue-800'
                }`}
              >
                {pair}
              </span>
            ))}
            {source.pairs.length > 6 && (
              <span className={`px-2 py-1 rounded text-xs ${
                isDarkMode ? 'text-gray-400' : 'text-gray-600'
              }`}>
                +{source.pairs.length - 6} more
              </span>
            )}
          </div>
        </div>

        <button
          onClick={() => onToggle(source.id)}
          className={`w-full py-2 px-4 rounded-lg font-medium transition-colors ${
            source.status === 'active'
              ? 'bg-red-500 hover:bg-red-600 text-white'
              : 'bg-blue-500 hover:bg-blue-600 text-white'
          }`}
        >
          {source.status === 'active' ? 'Stop Scraping' : 'Start Scraping'}
        </button>
      </div>
    </div>
  );
};