import React from 'react';
import { TrendingUp, Database, Globe, Clock } from 'lucide-react';

interface StatsCardsProps {
  isDarkMode: boolean;
}

export const StatsCards: React.FC<StatsCardsProps> = ({ isDarkMode }) => {
  const stats = [
    {
      title: 'Total Records',
      value: '1,234,567',
      change: '+12.5%',
      changeType: 'positive' as const,
      icon: Database,
      color: 'blue'
    },
    {
      title: 'Active Sources',
      value: '8',
      change: '+2',
      changeType: 'positive' as const,
      icon: Globe,
      color: 'green'
    },
    {
      title: 'Avg Response Time',
      value: '2.4s',
      change: '-0.3s',
      changeType: 'positive' as const,
      icon: Clock,
      color: 'purple'
    },
    {
      title: 'Success Rate',
      value: '98.7%',
      change: '+0.2%',
      changeType: 'positive' as const,
      icon: TrendingUp,
      color: 'orange'
    }
  ];

  const getColorClasses = (color: string) => {
    switch (color) {
      case 'blue':
        return 'bg-blue-500';
      case 'green':
        return 'bg-green-500';
      case 'purple':
        return 'bg-purple-500';
      case 'orange':
        return 'bg-orange-500';
      default:
        return 'bg-blue-500';
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {stats.map((stat, index) => (
        <div
          key={index}
          className={`rounded-xl border p-6 transition-all duration-200 hover:shadow-lg ${
            isDarkMode 
              ? 'bg-gray-800 border-gray-700 hover:shadow-gray-900/20' 
              : 'bg-white border-gray-200 hover:shadow-blue-100/50'
          }`}
        >
          <div className="flex items-center justify-between mb-4">
            <div className={`p-3 rounded-lg ${getColorClasses(stat.color)}`}>
              <stat.icon className="w-6 h-6 text-white" />
            </div>
            <span className={`text-sm font-medium ${
              stat.changeType === 'positive' ? 'text-green-600' : 'text-red-600'
            }`}>
              {stat.change}
            </span>
          </div>
          
          <div>
            <p className={`text-2xl font-bold mb-1 ${
              isDarkMode ? 'text-white' : 'text-gray-900'
            }`}>
              {stat.value}
            </p>
            <p className={`text-sm ${
              isDarkMode ? 'text-gray-400' : 'text-gray-600'
            }`}>
              {stat.title}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
};