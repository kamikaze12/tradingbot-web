import { useState, useEffect } from 'react';

export interface ForexData {
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

export interface DataSource {
  id: string;
  name: string;
  url: string;
  status: 'active' | 'error' | 'pending';
  lastUpdate: string;
  dataPoints: number;
  pairs: string[];
}

export interface ScrapingJob {
  id: string;
  source: string;
  status: 'running' | 'completed' | 'failed' | 'queued';
  progress: number;
  startTime: string;
  duration: string;
  recordsCollected: number;
  lastError?: string;
}

export const useForexData = () => {
  const [forexData, setForexData] = useState<ForexData[]>([]);
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [scrapingJobs, setScrapingJobs] = useState<ScrapingJob[]>([]);

  // Mock data generation
  useEffect(() => {
    const generateMockForexData = (): ForexData[] => {
      const pairs = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'USD/CHF', 'AUD/USD', 'USD/CAD', 'NZD/USD', 'EUR/GBP'];
      const sources = ['Yahoo Finance', 'XE.com', 'Investing.com', 'ForexFactory', 'OANDA'];
      
      return pairs.map(pair => ({
        pair,
        price: Math.random() * 2 + 0.5,
        change: (Math.random() - 0.5) * 0.02,
        changePercent: (Math.random() - 0.5) * 4,
        high: Math.random() * 2 + 0.6,
        low: Math.random() * 2 + 0.4,
        volume: Math.floor(Math.random() * 1000000) + 100000,
        source: sources[Math.floor(Math.random() * sources.length)],
        timestamp: new Date().toISOString()
      }));
    };

    const generateMockDataSources = (): DataSource[] => {
      return [
        {
          id: '1',
          name: 'Yahoo Finance',
          url: 'https://finance.yahoo.com/currencies',
          status: 'active',
          lastUpdate: '2 minutes ago',
          dataPoints: 15420,
          pairs: ['EUR/USD', 'GBP/USD', 'USD/JPY', 'USD/CHF', 'AUD/USD']
        },
        {
          id: '2',
          name: 'XE.com',
          url: 'https://www.xe.com/currencyconverter',
          status: 'active',
          lastUpdate: '5 minutes ago',
          dataPoints: 12350,
          pairs: ['EUR/USD', 'GBP/USD', 'USD/CAD', 'NZD/USD']
        },
        {
          id: '3',
          name: 'Investing.com',
          url: 'https://www.investing.com/currencies',
          status: 'error',
          lastUpdate: '1 hour ago',
          dataPoints: 8960,
          pairs: ['USD/JPY', 'EUR/GBP', 'AUD/USD', 'USD/CHF']
        },
        {
          id: '4',
          name: 'ForexFactory',
          url: 'https://www.forexfactory.com',
          status: 'pending',
          lastUpdate: '10 minutes ago',
          dataPoints: 6780,
          pairs: ['EUR/USD', 'GBP/USD', 'USD/JPY']
        }
      ];
    };

    const generateMockScrapingJobs = (): ScrapingJob[] => {
      return [
        {
          id: '1',
          source: 'Yahoo Finance',
          status: 'running',
          progress: 75,
          startTime: '10:30 AM',
          duration: '00:05:23',
          recordsCollected: 1250
        },
        {
          id: '2',
          source: 'XE.com',
          status: 'completed',
          progress: 100,
          startTime: '10:25 AM',
          duration: '00:03:45',
          recordsCollected: 890
        },
        {
          id: '3',
          source: 'Investing.com',
          status: 'failed',
          progress: 45,
          startTime: '10:20 AM',
          duration: '00:02:15',
          recordsCollected: 342,
          lastError: 'Rate limit exceeded'
        }
      ];
    };

    setForexData(generateMockForexData());
    setDataSources(generateMockDataSources());
    setScrapingJobs(generateMockScrapingJobs());

    // Simulate real-time updates
    const interval = setInterval(() => {
      setForexData(generateMockForexData());
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  const toggleDataSource = (id: string) => {
    setDataSources(prev => 
      prev.map(source => 
        source.id === id 
          ? { 
              ...source, 
              status: source.status === 'active' ? 'pending' : 'active' 
            }
          : source
      )
    );
  };

  return {
    forexData,
    dataSources,
    scrapingJobs,
    toggleDataSource
  };
};