import React, { useState } from 'react';
import { TrendingUp, TrendingDown, Search, Filter } from 'lucide-react';

interface ForexData {
  pair: string;
  price: number;
  change: number;
  changePercent: number;
  high: number;
  low: number;
  volume: number;
  source: string;
  timestamp: string;
}

interface ForexDataTableProps {
  data: ForexData[];
  isDarkMode: boolean;
}

export const ForexDataTable: React.FC<ForexDataTableProps> = ({ data, isDarkMode }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState<keyof ForexData>('pair');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  const filteredData = data.filter(item =>
    item.pair.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.source.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const sortedData = [...filteredData].sort((a, b) => {
    const aValue = a[sortBy];
    const bValue = b[sortBy];
    
    if (typeof aValue === 'string' && typeof bValue === 'string') {
      return sortOrder === 'asc' ? aValue.localeCompare(bValue) : bValue.localeCompare(aValue);
    }
    
    return sortOrder === 'asc' 
      ? (aValue as number) - (bValue as number)
      : (bValue as number) - (aValue as number);
  });

  const handleSort = (column: keyof ForexData) => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder('asc');
    }
  };

  return (
    <div className={`rounded-xl border ${
      isDarkMode 
        ? 'bg-gray-800 border-gray-700' 
        : 'bg-white border-gray-200'
    }`}>
      <div className="p-6 border-b border-gray-200 dark:border-gray-700">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-4 sm:space-y-0">
          <h2 className={`text-xl font-semibold ${
            isDarkMode ? 'text-white' : 'text-gray-900'
          }`}>
            Live Forex Data
          </h2>
          
          <div className="flex items-center space-x-4">
            <div className="relative">
              <Search className={`absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 ${
                isDarkMode ? 'text-gray-400' : 'text-gray-500'
              }`} />
              <input
                type="text"
                placeholder="Search pairs or sources..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className={`pl-10 pr-4 py-2 rounded-lg border transition-colors ${
                  isDarkMode 
                    ? 'bg-gray-700 border-gray-600 text-white placeholder-gray-400' 
                    : 'bg-gray-50 border-gray-300 text-gray-900 placeholder-gray-500'
                }`}
              />
            </div>
            
            <button className={`p-2 rounded-lg transition-colors ${
              isDarkMode 
                ? 'bg-gray-700 hover:bg-gray-600 text-gray-300' 
                : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
            }`}>
              <Filter className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className={`border-b ${
            isDarkMode ? 'border-gray-700' : 'border-gray-200'
          }`}>
            <tr>
              {[
                { key: 'pair', label: 'Pair' },
                { key: 'price', label: 'Price' },
                { key: 'change', label: 'Change' },
                { key: 'changePercent', label: 'Change %' },
                { key: 'high', label: '24h High' },
                { key: 'low', label: '24h Low' },
                { key: 'volume', label: 'Volume' },
                { key: 'source', label: 'Source' },
              ].map(({ key, label }) => (
                <th
                  key={key}
                  className={`px-6 py-3 text-left text-xs font-medium uppercase tracking-wider cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 ${
                    isDarkMode ? 'text-gray-300' : 'text-gray-500'
                  }`}
                  onClick={() => handleSort(key as keyof ForexData)}
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className={`divide-y ${
            isDarkMode ? 'divide-gray-700' : 'divide-gray-200'
          }`}>
            {sortedData.map((item, index) => (
              <tr
                key={index}
                className={`transition-colors ${
                  isDarkMode 
                    ? 'hover:bg-gray-700' 
                    : 'hover:bg-gray-50'
                }`}
              >
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center">
                    <span className={`font-medium ${
                      isDarkMode ? 'text-white' : 'text-gray-900'
                    }`}>
                      {item.pair}
                    </span>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`font-medium ${
                    isDarkMode ? 'text-white' : 'text-gray-900'
                  }`}>
                    ${item.price.toFixed(4)}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center">
                    {item.change >= 0 ? (
                      <TrendingUp className="w-4 h-4 text-green-500 mr-1" />
                    ) : (
                      <TrendingDown className="w-4 h-4 text-red-500 mr-1" />
                    )}
                    <span className={`font-medium ${
                      item.change >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {item.change >= 0 ? '+' : ''}{item.change.toFixed(4)}
                    </span>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`font-medium ${
                    item.changePercent >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {item.changePercent >= 0 ? '+' : ''}{item.changePercent.toFixed(2)}%
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={isDarkMode ? 'text-gray-300' : 'text-gray-700'}>
                    ${item.high.toFixed(4)}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={isDarkMode ? 'text-gray-300' : 'text-gray-700'}>
                    ${item.low.toFixed(4)}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={isDarkMode ? 'text-gray-300' : 'text-gray-700'}>
                    {item.volume.toLocaleString()}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    isDarkMode 
                      ? 'bg-blue-900 text-blue-300' 
                      : 'bg-blue-100 text-blue-800'
                  }`}>
                    {item.source}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};