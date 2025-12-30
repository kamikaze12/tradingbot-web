import React, { useState } from 'react';
import { Header } from './components/Header';
import { StatsCards } from './components/StatsCards';
import { DataSourceCard } from './components/DataSourceCard';
import { ForexDataTable } from './components/ForexDataTable';
import { ScrapingStatus } from './components/ScrapingStatus';
import { useForexData } from './hooks/useForexData';

function App() {
  const [isDarkMode, setIsDarkMode] = useState(false);
  const { forexData, dataSources, scrapingJobs, toggleDataSource } = useForexData();

  const toggleDarkMode = () => {
    setIsDarkMode(!isDarkMode);
  };

  return (
    <div className={`min-h-screen transition-colors duration-200 ${
      isDarkMode ? 'bg-gray-900' : 'bg-gray-50'
    }`}>
      <Header isDarkMode={isDarkMode} toggleDarkMode={toggleDarkMode} />
      
      <main className="container mx-auto px-6 py-8">
        <div className="space-y-8">
          {/* Stats Cards */}
          <StatsCards isDarkMode={isDarkMode} />
          
          {/* Data Sources Grid */}
          <div>
            <h2 className={`text-2xl font-bold mb-6 ${
              isDarkMode ? 'text-white' : 'text-gray-900'
            }`}>
              Data Sources
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {dataSources.map((source) => (
                <DataSourceCard
                  key={source.id}
                  source={source}
                  isDarkMode={isDarkMode}
                  onToggle={toggleDataSource}
                />
              ))}
            </div>
          </div>
          
          {/* Scraping Status and Forex Data */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-1">
              <ScrapingStatus jobs={scrapingJobs} isDarkMode={isDarkMode} />
            </div>
            <div className="lg:col-span-2">
              <ForexDataTable data={forexData} isDarkMode={isDarkMode} />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;