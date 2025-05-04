
import React, { useState, useEffect } from 'react';
import { 
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  Area, AreaChart, Scatter, ScatterChart, ZAxis
} from 'recharts';
import { Calendar, Clock, Download, Filter, RefreshCw, Save } from 'lucide-react';

// Color palette
const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#82CA9D', '#ffc658', '#8dd1e1'];

// Mock API service - would be replaced with actual API calls
const fetchData = async (endpoint, params) => {
  // In production, this would call your actual API
  // Example: return axios.get(`/api/v1/${endpoint}`, { params });
  
  // For demo purposes, returning mock data
  switch (endpoint) {
    case 'dashboard/summary':
      return getMockSummaryData();
    case 'metrics/timeseries':
      return getMockTimeseriesData(params);
    case 'anomalies/summary':
      return getMockAnomaliesData();
    case 'metrics/model-comparison':
      return getMockModelComparisonData();
    case 'hallucinations/stats':
      return getMockHallucinationData();
    case 'cost/optimization':
      return getMockCostOptimizationData();
    default:
      return {};
  }
};

// Mock data generators
const getMockSummaryData = () => ({
  total_requests: 12458,
  total_cost: 215.78,
  avg_inference_time: 0.873,
  success_rate: 0.992,
  error_rate: 0.008,
  total_tokens: 3426982,
  total_anomalies: 87,
  hallucination_rate: 0.034,
  top_models: [
    { provider: 'openai', model: 'gpt-4', request_count: 4502 },
    { provider: 'openai', model: 'gpt-3.5-turbo', request_count: 5623 },
    { provider: 'anthropic', model: 'claude-2', request_count: 1425 },
    { provider: 'anthropic', model: 'claude-instant-1', request_count: 908 }
  ],
  recent_anomalies: [
    { type: 'inference_time_spike', timestamp: '2025-05-04T08:12:34Z' },
    { type: 'high_token_usage', timestamp: '2025-05-03T22:45:12Z' },
    { type: 'potential_hallucination', timestamp: '2025-05-03T16:23:45Z' },
    { type: 'error_rate_spike', timestamp: '2025-05-02T14:34:56Z' }
  ],
  time_period: 'last_24h'
});

const getMockTimeseriesData = (params) => {
  const dataPoints = 24;
  const data = {
    labels: Array.from({ length: dataPoints }, (_, i) => `${i}:00`),
    datasets: {
      request_count: Array.from({ length: dataPoints }, () => Math.floor(Math.random() * 200) + 50),
      error_rate: Array.from({ length: dataPoints }, () => Math.random() * 0.05),
      avg_inference_time: Array.from({ length: dataPoints }, () => Math.random() * 1.5 + 0.5),
      total_tokens: Array.from({ length: dataPoints }, () => Math.floor(Math.random() * 100000) + 20000),
      total_cost: Array.from({ length: dataPoints }, () => Math.random() * 15 + 5)
    },
    interval: params?.interval || 'hour',
    start_time: params?.start_time || '2025-05-03T00:00:00Z',
    end_time: params?.end_time || '2025-05-04T00:00:00Z',
    point_count: dataPoints
  };
  return data;
};

const getMockAnomaliesData = () => ({
  total_anomalies: 87,
  by_type: [
    { type: 'inference_time_spike', count: 32 },
    { type: 'error_rate_spike', count: 18 },
    { type: 'high_token_usage', count: 15 },
    { type: 'potential_hallucination', count: 12 },
    { type: 'correlation_divergence', count: 6 },
    { type: 'other', count: 4 }
  ],
  by_model: [
    { provider: 'openai', model: 'gpt-4', count: 35 },
    { provider: 'openai', model: 'gpt-3.5-turbo', count: 28 },
    { provider: 'anthropic', model: 'claude-2', count: 14 },
    { provider: 'anthropic', model: 'claude-instant-1', count: 10 }
  ],
  by_day: [
    { date: '2025-04-28', count: 8 },
    { date: '2025-04-29', count: 12 },
    { date: '2025-04-30', count: 9 },
    { date: '2025-05-01', count: 15 },
    { date: '2025-05-02', count: 11 },
    { date: '2025-05-03', count: 14 },
    { date: '2025-05-04', count: 18 }
  ]
});

const getMockModelComparisonData = () => ({
  models: [
    { provider: 'openai', model: 'gpt-4' },
    { provider: 'openai', model: 'gpt-3.5-turbo' },
    { provider: 'anthropic', model: 'claude-2' },
    { provider: 'anthropic', model: 'claude-instant-1' }
  ],
  metrics: {
    avg_inference_time: [1.25, 0.65, 1.45, 0.78],
    error_rate: [0.005, 0.008, 0.007, 0.012],
    total_tokens_per_request: [850, 720, 920, 680],
    cost_per_request: [0.045, 0.009, 0.038, 0.012],
    cost_per_1k_tokens: [0.053, 0.013, 0.041, 0.018]
  },
  request_counts: [4502, 5623, 1425, 908]
});

const getMockHallucinationData = () => ({
  total_analyzed: 8500,
  hallucinations_detected: 289,
  detection_rate: 0.034,
  avg_score: 0.38,
  by_confidence: [
    { confidence: 'high', count: 68 },
    { confidence: 'medium', count: 112 },
    { confidence: 'low', count: 109 }
  ],
  by_reason: [
    { reason: 'uncertainty_phrases', count: 98 },
    { reason: 'contradictions', count: 87 },
    { reason: 'factual_errors', count: 54 },
    { reason: 'prompt_inconsistency', count: 32 },
    { reason: 'unusual_language_patterns', count: 18 }
  ],
  by_model: [
    { provider: 'openai', model: 'gpt-4', analyzed_count: 3200, detected_count: 86, detection_rate: 0.027, avg_score: 0.32 },
    { provider: 'openai', model: 'gpt-3.5-turbo', analyzed_count: 3800, detected_count: 152, detection_rate: 0.040, avg_score: 0.41 },
    { provider: 'anthropic', model: 'claude-2', analyzed_count: 980, detected_count: 24, detection_rate: 0.024, avg_score: 0.30 },
    { provider: 'anthropic', model: 'claude-instant-1', analyzed_count: 520, detected_count: 27, detection_rate: 0.052, avg_score: 0.45 }
  ]
});

const getMockCostOptimizationData = () => ({
  status: 'success',
  recommendations: [
    { 
      type: 'model_switch', 
      message: 'Consider using gpt-3.5-turbo instead of gpt-4 for non-critical tasks',
      estimated_savings: 95.42,
      severity: 'high'
    },
    { 
      type: 'caching', 
      message: 'Implement response caching for frequently repeated prompts',
      estimated_savings: 43.27,
      severity: 'medium'
    },
    { 
      type: 'batching', 
      message: 'Batch small requests to reduce API call overhead',
      estimated_savings: 28.15,
      severity: 'medium'
    },
    { 
      type: 'prompt_optimization', 
      message: 'Optimize prompts to reduce token usage',
      estimated_savings: 18.90,
      severity: 'medium'
    }
  ],
  total_potential_savings: 185.74,
  current_monthly_cost: 654.32
});

// Dashboard component
const Dashboard = () => {
  // State for filters and data
  const [timeRange, setTimeRange] = useState({ 
    start: new Date(Date.now() - 24*60*60*1000), 
    end: new Date() 
  });
  const [filters, setFilters] = useState({
    provider: 'all',
    model: 'all',
    application: 'all',
    environment: 'production'
  });
  const [dashboardType, setDashboardType] = useState('overview'); // overview, performance, cost, quality
  const [isLoading, setIsLoading] = useState(true);
  const [summaryData, setSummaryData] = useState(null);
  const [timeseriesData, setTimeseriesData] = useState(null);
  const [anomaliesData, setAnomaliesData] = useState(null);
  const [modelComparisonData, setModelComparisonData] = useState(null);
  const [hallucinationData, setHallucinationData] = useState(null);
  const [costOptimizationData, setCostOptimizationData] = useState(null);
  const [refreshInterval, setRefreshInterval] = useState(null);

  // Custom formatter for numbers
  const formatNumber = (num) => {
    if (num === null || num === undefined) return '-';
    if (num >= 1000000) return `${(num/1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num/1000).toFixed(1)}K`;
    return num.toFixed(2);
  };

  // Format cost values
  const formatCost = (cost) => {
    return `$${cost.toFixed(2)}`;
  };

  // Format percentage values
  const formatPercent = (value) => {
    return `${(value * 100).toFixed(2)}%`;
  };

  // Load dashboard data
  const loadDashboardData = async () => {
    setIsLoading(true);
    try {
      // Convert timeRange to ISO strings for API
      const start_time = timeRange.start.toISOString();
      const end_time = timeRange.end.toISOString();
      
      // Prepare params with filters
      const params = {
        start_time,
        end_time,
        ...Object.entries(filters)
          .filter(([_, value]) => value !== 'all')
          .reduce((acc, [key, value]) => ({ ...acc, [key]: value }), {})
      };
      
      // Fetch summary data
      const summary = await fetchData('dashboard/summary', params);
      setSummaryData(summary);
      
      // Fetch time series data
      const timeseries = await fetchData('metrics/timeseries', {
        ...params,
        interval: getTimeInterval(timeRange)
      });
      setTimeseriesData(timeseries);
      
      // Fetch anomalies data
      const anomalies = await fetchData('anomalies/summary', params);
      setAnomaliesData(anomalies);
      
      // Fetch model comparison data
      const modelComparison = await fetchData('metrics/model-comparison', {
        models: summary?.top_models?.map(m => ({ provider: m.provider, model: m.model })) || [],
        ...params
      });
      setModelComparisonData(modelComparison);
      
      // Fetch hallucination data if needed for quality dashboard
      if (dashboardType === 'quality') {
        const hallucinations = await fetchData('hallucinations/stats', params);
        setHallucinationData(hallucinations);
      }
      
      // Fetch cost optimization data if needed for cost dashboard
      if (dashboardType === 'cost') {
        const costOptimization = await fetchData('cost/optimization', params);
        setCostOptimizationData(costOptimization);
      }
    } catch (error) {
      console.error('Error loading dashboard data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Determine time interval based on date range
  const getTimeInterval = (range) => {
    const diffHours = (range.end - range.start) / (1000 * 60 * 60);
    if (diffHours <= 6) return 'minute';
    if (diffHours <= 48) return 'hour';
    if (diffHours <= 168) return 'day';
    return 'week';
  };

  // Setup data loading on component mount and when filters/timeRange change
  useEffect(() => {
    loadDashboardData();
    
    // Setup refresh interval if active
    if (refreshInterval) {
      const interval = setInterval(loadDashboardData, refreshInterval * 1000);
      return () => clearInterval(interval);
    }
  }, [timeRange, filters, dashboardType, refreshInterval]);

  // Prepare time series data for charts
  const prepareChartData = (metric) => {
    if (!timeseriesData) return [];
    
    return timeseriesData.labels.map((label, index) => ({
      name: label,
      value: timeseriesData.datasets[metric][index]
    }));
  };

  // Handle time range change
  const handleTimeRangeChange = (range) => {
    setTimeRange(range);
  };

  // Handle filter change
  const handleFilterChange = (name, value) => {
    setFilters(prev => ({ ...prev, [name]: value }));
  };

  // Handle dashboard type change
  const handleDashboardTypeChange = (type) => {
    setDashboardType(type);
  };

  // Handle dashboard export
  const handleExportDashboard = () => {
    const dashboardData = {
      timeRange,
      filters,
      dashboardType,
      summaryData,
      timeseriesData,
      anomaliesData,
      modelComparisonData,
      hallucinationData,
      costOptimizationData
    };
    
    const blob = new Blob([JSON.stringify(dashboardData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sentinelops-dashboard-${dashboardType}-${new Date().toISOString()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Import dashboard configuration
  const handleImportDashboard = (event) => {
    const file = event.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const importedData = JSON.parse(e.target.result);
        if (importedData.timeRange) setTimeRange(importedData.timeRange);
        if (importedData.filters) setFilters(importedData.filters);
        if (importedData.dashboardType) setDashboardType(importedData.dashboardType);
      } catch (error) {
        console.error('Error importing dashboard:', error);
        alert('Invalid dashboard configuration file');
      }
    };
    reader.readAsText(file);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Dashboard Controls */}
      <div className="flex flex-col md:flex-row justify-between items-center p-4 bg-white border-b border-gray-200">
        <div className="flex items-center space-x-4 mb-4 md:mb-0">
          <h1 className="text-xl font-bold">
            {dashboardType === 'overview' && 'Overview Dashboard'}
            {dashboardType === 'performance' && 'Performance Dashboard'}
            {dashboardType === 'cost' && 'Cost & Optimization Dashboard'}
            {dashboardType === 'quality' && 'Quality & Hallucinations Dashboard'}
          </h1>
          
          <div className="flex space-x-2">
            <button 
              className={`px-3 py-1 text-sm rounded ${dashboardType === 'overview' ? 'bg-blue-500 text-white' : 'bg-gray-200'}`}
              onClick={() => handleDashboardTypeChange('overview')}
            >
              Overview
            </button>
            <button 
              className={`px-3 py-1 text-sm rounded ${dashboardType === 'performance' ? 'bg-blue-500 text-white' : 'bg-gray-200'}`}
              onClick={() => handleDashboardTypeChange('performance')}
            >
              Performance
            </button>
            <button 
              className={`px-3 py-1 text-sm rounded ${dashboardType === 'cost' ? 'bg-blue-500 text-white' : 'bg-gray-200'}`}
              onClick={() => handleDashboardTypeChange('cost')}
            >
              Cost
            </button>
            <button 
              className={`px-3 py-1 text-sm rounded ${dashboardType === 'quality' ? 'bg-blue-500 text-white' : 'bg-gray-200'}`}
              onClick={() => handleDashboardTypeChange('quality')}
            >
              Quality
            </button>
          </div>
        </div>
        
        <div className="flex items-center space-x-3">
          <div className="flex items-center">
            <button 
              className="p-2 rounded bg-gray-100 hover:bg-gray-200"
              onClick={loadDashboardData}
              title="Refresh data"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
          
          <div className="flex items-center">
            <select 
              className="p-2 border rounded text-sm"
              value={refreshInterval || ''}
              onChange={(e) => setRefreshInterval(e.target.value ? parseInt(e.target.value) : null)}
              title="Auto-refresh interval"
            >
              <option value="">Manual refresh</option>
              <option value="30">30 seconds</option>
              <option value="60">1 minute</option>
              <option value="300">5 minutes</option>
              <option value="900">15 minutes</option>
            </select>
          </div>
          
          <div className="flex items-center">
            <button 
              className="p-2 rounded bg-gray-100 hover:bg-gray-200"
              onClick={handleExportDashboard}
              title="Export dashboard"
            >
              <Download className="w-4 h-4" />
            </button>
          </div>
          
          <div className="flex items-center">
            <label className="p-2 rounded bg-gray-100 hover:bg-gray-200 cursor-pointer">
              <input
                type="file"
                className="hidden"
                accept=".json"
                onChange={handleImportDashboard}
              />
              <Save className="w-4 h-4" />
            </label>
          </div>
        </div>
      </div>
      
      {/* Filters Section */}
      <div className="bg-gray-50 p-4 border-b border-gray-200 flex flex-wrap items-center gap-4">
        <div className="flex items-center">
          <Filter className="w-4 h-4 mr-2 text-gray-500" />
          <span className="text-sm font-medium">Filters:</span>
        </div>
        
        <div className="flex items-center space-x-2">
          <select 
            className="p-2 text-sm border rounded"
            value={filters.provider}
            onChange={(e) => handleFilterChange('provider', e.target.value)}
          >
            <option value="all">All Providers</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="cohere">Cohere</option>
            <option value="huggingface">Hugging Face</option>
          </select>
          
          <select 
            className="p-2 text-sm border rounded"
            value={filters.model}
            onChange={(e) => handleFilterChange('model', e.target.value)}
          >
            <option value="all">All Models</option>
            <option value="gpt-4">GPT-4</option>
            <option value="gpt-3.5-turbo">GPT-3.5-Turbo</option>
            <option value="claude-2">Claude 2</option>
            <option value="claude-instant-1">Claude Instant</option>
          </select>
          
          <select 
            className="p-2 text-sm border rounded"
            value={filters.application}
            onChange={(e) => handleFilterChange('application', e.target.value)}
          >
            <option value="all">All Applications</option>
            <option value="chatbot">Chatbot</option>
            <option value="content-generator">Content Generator</option>
            <option value="customer-support">Customer Support</option>
            <option value="research-assistant">Research Assistant</option>
          </select>
          
          <select 
            className="p-2 text-sm border rounded"
            value={filters.environment}
            onChange={(e) => handleFilterChange('environment', e.target.value)}
          >
            <option value="all">All Environments</option>
            <option value="production">Production</option>
            <option value="staging">Staging</option>
            <option value="development">Development</option>
            <option value="test">Test</option>
          </select>
        </div>
        
        <div className="flex items-center space-x-2 ml-auto">
          <Calendar className="w-4 h-4 text-gray-500" />
          <select 
            className="p-2 text-sm border rounded"
            value={
              timeRange.end.getTime() - timeRange.start.getTime() === 24*60*60*1000 ? "24h" :
              timeRange.end.getTime() - timeRange.start.getTime() === 7*24*60*60*1000 ? "7d" :
              timeRange.end.getTime() - timeRange.start.getTime() === 30*24*60*60*1000 ? "30d" : "custom"
            }
            onChange={(e) => {
              const now = new Date();
              switch(e.target.value) {
                case "24h":
                  setTimeRange({ start: new Date(now.getTime() - 24*60*60*1000), end: now });
                  break;
                case "7d":
                  setTimeRange({ start: new Date(now.getTime() - 7*24*60*60*1000), end: now });
                  break;
                case "30d":
                  setTimeRange({ start: new Date(now.getTime() - 30*24*60*60*1000), end: now });
                  break;
                default:
                  // Custom range - could show a date picker
                  break;
              }
            }}
          >
            <option value="24h">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="custom">Custom range</option>
          </select>
        </div>
      </div>
      
      {/* Dashboard Content */}
      <div className="flex-grow p-4 overflow-auto">
        {isLoading ? (
          <div className="flex justify-center items-center h-full">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
          </div>
        ) : (
          <>
            {/* Overview Dashboard */}
            {dashboardType === 'overview' && (
              <div className="space-y-6">
                {/* Summary Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-sm font-medium text-gray-500">Total Requests</h3>
                    <div className="mt-2 flex justify-between items-end">
                      <p className="text-3xl font-bold">{formatNumber(summaryData?.total_requests)}</p>
                      <div className="flex items-center text-xs">
                        <Clock className="w-3 h-3 mr-1" />
                        <span>Last 24h</span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-sm font-medium text-gray-500">Success Rate</h3>
                    <div className="mt-2 flex justify-between items-end">
                      <p className="text-3xl font-bold">{formatPercent(summaryData?.success_rate)}</p>
                      <div className="flex items-center text-xs">
                        <div className={`w-2 h-2 rounded-full mr-1 ${summaryData?.success_rate > 0.99 ? 'bg-green-500' : summaryData?.success_rate > 0.95 ? 'bg-yellow-500' : 'bg-red-500'}`}></div>
                        <span>{summaryData?.success_rate > 0.99 ? 'Excellent' : summaryData?.success_rate > 0.95 ? 'Good' : 'Needs Attention'}</span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-sm font-medium text-gray-500">Avg. Inference Time</h3>
                    <div className="mt-2 flex justify-between items-end">
                      <p className="text-3xl font-bold">{summaryData?.avg_inference_time.toFixed(3)}s</p>
                      <div className="flex items-center text-xs">
                        <div className={`w-2 h-2 rounded-full mr-1 ${summaryData?.avg_inference_time < 1 ? 'bg-green-500' : summaryData?.avg_inference_time < 2 ? 'bg-yellow-500' : 'bg-red-500'}`}></div>
                        <span>{summaryData?.avg_inference_time < 1 ? 'Fast' : summaryData?.avg_inference_time < 2 ? 'Moderate' : 'Slow'}</span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-sm font-medium text-gray-500">Total Cost</h3>
                    <div className="mt-2 flex justify-between items-end">
                      <p className="text-3xl font-bold">{formatCost(summaryData?.total_cost)}</p>
                      <div className="flex items-center text-xs">
                        <Clock className="w-3 h-3 mr-1" />
                        <span>Last 24h</span>
                      </div>
                    </div>
                  </div>
                </div>
                
                {/* Charts Row */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {/* Requests Over Time */}
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-base font-medium mb-4">Requests Over Time</h3>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={prepareChartData('request_count')}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" />
                          <YAxis />
                          <Tooltip />
                          <Area type="monotone" dataKey="value" stroke="#0088FE" fill="#0088FE" fillOpacity={0.3} />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  {/* Error Rate Over Time */}
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-base font-medium mb-4">Error Rate Over Time</h3>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={prepareChartData('error_rate')}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" />
                          <YAxis tickFormatter={(value) => `${(value * 100).toFixed(1)}%`} />
                          <Tooltip formatter={(value) => [`${(value * 100).toFixed(2)}%`, 'Error Rate']} />
                          <Line type="monotone" dataKey="value" stroke="#FF8042" strokeWidth={2} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </div>
                
                {/* Bottom Row - Model Usage and Anomalies */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {/* Model Usage */}
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-base font-medium mb-4">Model Usage Distribution</h3>
                    <div className="h-64 flex items-center justify-center">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={summaryData?.top_models?.map(model => ({
                              name: `${model.provider}/${model.model}`,
                              value: model.request_count
                            })) || []}
                            cx="50%"
                            cy="50%"
                            labelLine={false}
                            outerRadius={80}
                            fill="#8884d8"
                            dataKey="value"
                            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                          >
                            {(summaryData?.top_models || []).map((_, index) => (
                              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip formatter={(value) => [value, 'Requests']} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                  
                  {/* Recent Anomalies */}
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-base font-medium mb-4">Recent Anomalies</h3>
                    <div className="overflow-hidden">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {(summaryData?.recent_anomalies || []).map((anomaly, index) => (
                            <tr key={index} className="hover:bg-gray-50">
                              <td className="px-6 py-4 whitespace-nowrap">
                                <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full 
                                  ${anomaly.type.includes('error') ? 'bg-red-100 text-red-800' : 
                                    anomaly.type.includes('time') ? 'bg-yellow-100 text-yellow-800' : 
                                    anomaly.type.includes('token') ? 'bg-blue-100 text-blue-800' : 
                                    anomaly.type.includes('hallucination') ? 'bg-purple-100 text-purple-800' : 
                                    'bg-gray-100 text-gray-800'}`}>
                                  {anomaly.type.replace(/_/g, ' ')}
                                </span>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                {new Date(anomaly.timestamp).toLocaleString()}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>
            )}
            
            {/* Performance Dashboard */}
            {dashboardType === 'performance' && (
              <div className="space-y-6">
                {/* Performance Summary Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-sm font-medium text-gray-500">Avg. Inference Time</h3>
                    <div className="mt-2 flex justify-between items-end">
                      <p className="text-3xl font-bold">{summaryData?.avg_inference_time.toFixed(3)}s</p>
                      <div className="flex items-center text-xs">
                        <div className={`w-2 h-2 rounded-full mr-1 ${summaryData?.avg_inference_time < 1 ? 'bg-green-500' : summaryData?.avg_inference_time < 2 ? 'bg-yellow-500' : 'bg-red-500'}`}></div>
                        <span>{summaryData?.avg_inference_time < 1 ? 'Fast' : summaryData?.avg_inference_time < 2 ? 'Moderate' : 'Slow'}</span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-sm font-medium text-gray-500">Throughput</h3>
                    <div className="mt-2 flex justify-between items-end">
                      <p className="text-3xl font-bold">{formatNumber(summaryData?.total_requests / 24)}/h</p>
                    </div>
                  </div>
                  
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-sm font-medium text-gray-500">Success Rate</h3>
                    <div className="mt-2 flex justify-between items-end">
                      <p className="text-3xl font-bold">{formatPercent(summaryData?.success_rate)}</p>
                      <div className="flex items-center text-xs">
                        <div className={`w-2 h-2 rounded-full mr-1 ${summaryData?.success_rate > 0.99 ? 'bg-green-500' : summaryData?.success_rate > 0.95 ? 'bg-yellow-500' : 'bg-red-500'}`}></div>
                        <span>{summaryData?.success_rate > 0.99 ? 'Excellent' : summaryData?.success_rate > 0.95 ? 'Good' : 'Needs Attention'}</span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-sm font-medium text-gray-500">Anomalies</h3>
                    <div className="mt-2 flex justify-between items-end">
                      <p className="text-3xl font-bold">{summaryData?.total_anomalies}</p>
                      <div className="flex items-center text-xs">
                        <div className={`w-2 h-2 rounded-full mr-1 ${summaryData?.total_anomalies < 10 ? 'bg-green-500' : summaryData?.total_anomalies < 50 ? 'bg-yellow-500' : 'bg-red-500'}`}></div>
                        <span>{summaryData?.total_anomalies < 10 ? 'Low' : summaryData?.total_anomalies < 50 ? 'Moderate' : 'High'}</span>
                      </div>
                    </div>
                  </div>
                </div>
                
                {/* Performance Charts */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {/* Inference Time Over Time */}
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-base font-medium mb-4">Inference Time Over Time</h3>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={prepareChartData('avg_inference_time')}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" />
                          <YAxis domain={[0, 'auto']} />
                          <Tooltip formatter={(value) => [`${value.toFixed(3)}s`, 'Avg Inference Time']} />
                          <Line type="monotone" dataKey="value" stroke="#00C49F" strokeWidth={2} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                  
                  {/* Request Volume Over Time */}
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-base font-medium mb-4">Request Volume Over Time</h3>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={prepareChartData('request_count')}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" />
                          <YAxis />
                          <Tooltip />
                          <Bar dataKey="value" name="Requests" fill="#8884d8" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </div>
                
                {/* Model Comparison */}
                <div className="bg-white p-4 rounded-lg shadow">
                  <h3 className="text-base font-medium mb-4">Model Performance Comparison</h3>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={(modelComparisonData?.models || []).map((model, index) => ({
                          name: `${model.provider}/${model.model}`,
                          inferenceTime: modelComparisonData.metrics.avg_inference_time[index],
                          errorRate: modelComparisonData.metrics.error_rate[index] * 100,
                          requestCount: modelComparisonData.request_counts[index]
                        }))}
                        margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="name" />
                        <YAxis yAxisId="left" orientation="left" label={{ value: 'Inference Time (s)', angle: -90, position: 'insideLeft' }} />
                        <YAxis yAxisId="right" orientation="right" label={{ value: 'Error Rate (%)', angle: 90, position: 'insideRight' }} />
                        <Tooltip />
                        <Legend />
                        <Bar yAxisId="left" dataKey="inferenceTime" name="Inference Time (s)" fill="#0088FE" />
                        <Bar yAxisId="right" dataKey="errorRate" name="Error Rate (%)" fill="#FF8042" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
                
                {/* Anomalies By Type */}
                <div className="bg-white p-4 rounded-lg shadow">
                  <h3 className="text-base font-medium mb-4">Anomalies By Type</h3>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={(anomaliesData?.by_type || []).map(item => ({
                            name: item.type.replace(/_/g, ' '),
                            value: item.count
                          }))}
                          cx="50%"
                          cy="50%"
                          labelLine={false}
                          outerRadius={80}
                          fill="#8884d8"
                          dataKey="value"
                          label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                        >
                          {(anomaliesData?.by_type || []).map((_, index) => (
                            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip formatter={(value) => [value, 'Count']} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            )}

            {/* Cost Dashboard */}
            {dashboardType === 'cost' && (
              <div className="space-y-6">
                {/* Cost Summary Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-sm font-medium text-gray-500">Total Cost</h3>
                    <div className="mt-2 flex justify-between items-end">
                      <p className="text-3xl font-bold">{formatCost(summaryData?.total_cost)}</p>
                      <div className="flex items-center text-xs">
                        <Clock className="w-3 h-3 mr-1" />
                        <span>Last 24h</span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-sm font-medium text-gray-500">Cost per Request</h3>
                    <div className="mt-2 flex justify-between items-end">
                      <p className="text-3xl font-bold">{formatCost(summaryData?.total_cost / summaryData?.total_requests)}</p>
                    </div>
                  </div>
                  
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-sm font-medium text-gray-500">Total Tokens</h3>
                    <div className="mt-2 flex justify-between items-end">
                      <p className="text-3xl font-bold">{formatNumber(summaryData?.total_tokens)}</p>
                    </div>
                  </div>
                  
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-sm font-medium text-gray-500">Potential Savings</h3>
                    <div className="mt-2 flex justify-between items-end">
                      <p className="text-3xl font-bold">{formatCost(costOptimizationData?.total_potential_savings || 0)}</p>
                      <div className="flex items-center text-xs">
                        <div className="w-2 h-2 rounded-full mr-1 bg-green-500"></div>
                        <span>Opportunity</span>
                      </div>
                    </div>
                  </div>
                </div>
                
                {/* Cost Charts */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {/* Cost Over Time */}
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-base font-medium mb-4">Cost Over Time</h3>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={prepareChartData('total_cost')}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" />
                          <YAxis tickFormatter={(value) => `${value.toFixed(2)}`} />
                          <Tooltip formatter={(value) => [`${value.toFixed(2)}`, 'Cost']} />
                          <Area type="monotone" dataKey="value" stroke="#8884d8" fill="#8884d8" fillOpacity={0.3} />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                  
                  {/* Token Usage Over Time */}
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-base font-medium mb-4">Token Usage Over Time</h3>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={prepareChartData('total_tokens')}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" />
                          <YAxis />
                          <Tooltip formatter={(value) => [formatNumber(value), 'Tokens']} />
                          <Area type="monotone" dataKey="value" stroke="#00C49F" fill="#00C49F" fillOpacity={0.3} />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </div>
                
                {/* Cost By Model */}
                <div className="bg-white p-4 rounded-lg shadow">
                  <h3 className="text-base font-medium mb-4">Cost Comparison By Model</h3>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={(modelComparisonData?.models || []).map((model, index) => ({
                          name: `${model.provider}/${model.model}`,
                          costPerRequest: modelComparisonData.metrics.cost_per_request[index],
                          costPer1kTokens: modelComparisonData.metrics.cost_per_1k_tokens[index],
                          tokensPerRequest: modelComparisonData.metrics.total_tokens_per_request[index],
                          requests: modelComparisonData.request_counts[index]
                        }))}
                        margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="name" />
                        <YAxis yAxisId="left" orientation="left" tickFormatter={(value) => `${value.toFixed(3)}`} label={{ value: 'Cost per Request', angle: -90, position: 'insideLeft' }} />
                        <YAxis yAxisId="right" orientation="right" tickFormatter={(value) => `${value.toFixed(3)}`} label={{ value: 'Cost per 1K Tokens', angle: 90, position: 'insideRight' }} />
                        <Tooltip formatter={(value, name) => [`${value.toFixed(4)}`, name]} />
                        <Legend />
                        <Bar yAxisId="left" dataKey="costPerRequest" name="Cost per Request" fill="#0088FE" />
                        <Bar yAxisId="right" dataKey="costPer1kTokens" name="Cost per 1K Tokens" fill="#FFBB28" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
                
                {/* Cost Optimization Recommendations */}
                <div className="bg-white p-4 rounded-lg shadow">
                  <h3 className="text-base font-medium mb-4">Cost Optimization Recommendations</h3>
                  <div className="overflow-hidden">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Recommendation</th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Estimated Savings</th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Severity</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {(costOptimizationData?.recommendations || []).map((rec, index) => (
                          <tr key={index} className="hover:bg-gray-50">
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                              {rec.message}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                              {formatCost(rec.estimated_savings)}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full 
                                ${rec.severity === 'high' ? 'bg-red-100 text-red-800' : 
                                  rec.severity === 'medium' ? 'bg-yellow-100 text-yellow-800' : 
                                  'bg-green-100 text-green-800'}`}>
                                {rec.severity}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
                  
            {/* Quality Dashboard */}
            {dashboardType === 'quality' && (
              <div className="space-y-6">
                {/* Quality Summary Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-sm font-medium text-gray-500">Success Rate</h3>
                    <div className="mt-2 flex justify-between items-end">
                      <p className="text-3xl font-bold">{formatPercent(summaryData?.success_rate)}</p>
                      <div className="flex items-center text-xs">
                        <div className={`w-2 h-2 rounded-full mr-1 ${summaryData?.success_rate > 0.99 ? 'bg-green-500' : summaryData?.success_rate > 0.95 ? 'bg-yellow-500' : 'bg-red-500'}`}></div>
                        <span>{summaryData?.success_rate > 0.99 ? 'Excellent' : summaryData?.success_rate > 0.95 ? 'Good' : 'Needs Attention'}</span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-sm font-medium text-gray-500">Hallucination Rate</h3>
                    <div className="mt-2 flex justify-between items-end">
                      <p className="text-3xl font-bold">{formatPercent(hallucinationData?.detection_rate || 0)}</p>
                      <div className="flex items-center text-xs">
                        <div className={`w-2 h-2 rounded-full mr-1 ${(hallucinationData?.detection_rate || 0) < 0.02 ? 'bg-green-500' : (hallucinationData?.detection_rate || 0) < 0.05 ? 'bg-yellow-500' : 'bg-red-500'}`}></div>
                        <span>{(hallucinationData?.detection_rate || 0) < 0.02 ? 'Low' : (hallucinationData?.detection_rate || 0) < 0.05 ? 'Moderate' : 'High'}</span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-sm font-medium text-gray-500">Analyzed Requests</h3>
                    <div className="mt-2 flex justify-between items-end">
                      <p className="text-3xl font-bold">{formatNumber(hallucinationData?.total_analyzed || 0)}</p>
                    </div>
                  </div>
                  
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-sm font-medium text-gray-500">Avg Hallucination Score</h3>
                    <div className="mt-2 flex justify-between items-end">
                      <p className="text-3xl font-bold">{(hallucinationData?.avg_score || 0).toFixed(2)}</p>
                      <div className="flex items-center text-xs">
                        <div className={`w-2 h-2 rounded-full mr-1 ${(hallucinationData?.avg_score || 0) < 0.3 ? 'bg-green-500' : (hallucinationData?.avg_score || 0) < 0.5 ? 'bg-yellow-500' : 'bg-red-500'}`}></div>
                        <span>{(hallucinationData?.avg_score || 0) < 0.3 ? 'Low' : (hallucinationData?.avg_score || 0) < 0.5 ? 'Moderate' : 'High'}</span>
                      </div>
                    </div>
                  </div>
                </div>
                
                {/* Hallucination Charts */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {/* Hallucinations by Confidence */}
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-base font-medium mb-4">Hallucinations by Confidence Level</h3>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={(hallucinationData?.by_confidence || []).map(item => ({
                              name: item.confidence,
                              value: item.count
                            }))}
                            cx="50%"
                            cy="50%"
                            labelLine={false}
                            outerRadius={80}
                            fill="#8884d8"
                            dataKey="value"
                            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                          >
                            <Cell key="cell-high" fill="#FF8042" />
                            <Cell key="cell-medium" fill="#FFBB28" />
                            <Cell key="cell-low" fill="#00C49F" />
                          </Pie>
                          <Tooltip formatter={(value) => [value, 'Count']} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                  
                  {/* Hallucinations by Reason */}
                  <div className="bg-white p-4 rounded-lg shadow">
                    <h3 className="text-base font-medium mb-4">Hallucinations by Reason</h3>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart 
                          data={(hallucinationData?.by_reason || []).map(item => ({
                            name: item.reason.replace(/_/g, ' '),
                            count: item.count
                          }))}
                          layout="vertical"
                          margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis type="number" />
                          <YAxis dataKey="name" type="category" width={150} />
                          <Tooltip formatter={(value) => [value, 'Count']} />
                          <Bar dataKey="count" fill="#8884D8" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </div>
                
                {/* Hallucination Rates By Model */}
                <div className="bg-white p-4 rounded-lg shadow">
                  <h3 className="text-base font-medium mb-4">Hallucination Rates By Model</h3>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={(hallucinationData?.by_model || []).map(model => ({
                          name: `${model.provider}/${model.model}`,
                          detectionRate: model.detection_rate * 100,
                          avgScore: model.avg_score,
                          analyzedCount: model.analyzed_count
                        }))}
                        margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="name" />
                        <YAxis yAxisId="left" orientation="left" tickFormatter={(value) => `${value.toFixed(1)}%`} label={{ value: 'Detection Rate (%)', angle: -90, position: 'insideLeft' }} />
                        <YAxis yAxisId="right" orientation="right" domain={[0, 1]} label={{ value: 'Avg Score', angle: 90, position: 'insideRight' }} />
                        <Tooltip formatter={(value, name) => [name === 'detectionRate' ? `${value.toFixed(2)}%` : name === 'avgScore' ? value.toFixed(2) : value, name === 'detectionRate' ? 'Detection Rate' : name === 'avgScore' ? 'Avg Score' : 'Analyzed Count']} />
                        <Legend />
                        <Bar yAxisId="left" dataKey="detectionRate" name="Detection Rate (%)" fill="#FF8042" />
                        <Bar yAxisId="right" dataKey="avgScore" name="Avg Score" fill="#0088FE" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
                
                {/* Model Comparison Scatter Plot */}
                <div className="bg-white p-4 rounded-lg shadow">
                  <h3 className="text-base font-medium mb-4">Model Quality Comparison</h3>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <ScatterChart
                        margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis type="number" dataKey="errorRate" name="Error Rate" unit="%" domain={[0, 'auto']} label={{ value: 'Error Rate (%)', position: 'bottom' }} />
                        <YAxis type="number" dataKey="hallucinationRate" name="Hallucination Rate" unit="%" domain={[0, 'auto']} label={{ value: 'Hallucination Rate (%)', angle: -90, position: 'insideLeft' }} />
                        <ZAxis type="number" dataKey="requestCount" range={[50, 500]} />
                        <Tooltip cursor={{ strokeDasharray: '3 3' }} formatter={(value, name) => [name === 'errorRate' || name === 'hallucinationRate' ? `${value.toFixed(2)}%` : value, name === 'errorRate' ? 'Error Rate' : name === 'hallucinationRate' ? 'Hallucination Rate' : 'Request Count']} />
                        <Legend />
                        <Scatter
                          name="Models"
                          data={[
                            ...(hallucinationData?.by_model || []).map((model, index) => {
                              const matchingModel = (modelComparisonData?.models || []).findIndex(m => 
                                m.provider === model.provider && m.model === model.model
                              );
                              
                              return {
                                name: `${model.provider}/${model.model}`,
                                errorRate: matchingModel !== -1 ? modelComparisonData.metrics.error_rate[matchingModel] * 100 : 0,
                                hallucinationRate: model.detection_rate * 100,
                                requestCount: model.analyzed_count,
                                fill: COLORS[index % COLORS.length]
                              };
                            })
                          ]}
                          fill="#8884d8"
                        />
                      </ScatterChart>
                    </ResponsiveContainer>
                  </div>
                </div>
                
                {/* Analyzed Content */}
                <div className="bg-white p-4 rounded-lg shadow">
                  <h3 className="text-base font-medium mb-4">Content Analysis</h3>
                  <p className="text-gray-700 mb-4">
                    SentinelOps has analyzed {formatNumber(hallucinationData?.total_analyzed || 0)} responses across 
                    {hallucinationData?.by_model?.length || 0} different models, detecting 
                    {formatNumber(hallucinationData?.hallucinations_detected || 0)} potential hallucinations.
                  </p>
                  <div className="flex flex-col md:flex-row gap-4">
                    <div className="bg-gray-50 p-4 rounded-lg flex-1">
                      <h4 className="text-sm font-medium text-gray-700 mb-2">Most Common Hallucination Patterns</h4>
                      <ul className="list-disc list-inside text-sm">
                        {(hallucinationData?.by_reason || []).slice(0, 5).map((reason, index) => (
                          <li key={index} className="mb-1">
                            <span className="font-medium">{reason.reason.replace(/_/g, ' ')}</span>: 
                            <span className="text-gray-600 ml-1">{reason.count} occurrences</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div className="bg-gray-50 p-4 rounded-lg flex-1">
                      <h4 className="text-sm font-medium text-gray-700 mb-2">Quality Recommendations</h4>
                      <ul className="list-disc list-inside text-sm">
                        <li className="mb-1">
                          <span className="font-medium">Use Structured Prompts</span>: 
                          <span className="text-gray-600 ml-1">Reduces uncertainty markers by 45%</span>
                        </li>
                        <li className="mb-1">
                          <span className="font-medium">Include References</span>: 
                          <span className="text-gray-600 ml-1">Decreases factual errors by 67%</span>
                        </li>
                        <li className="mb-1">
                          <span className="font-medium">Add Context</span>: 
                          <span className="text-gray-600 ml-1">Reduces prompt inconsistency by 53%</span>
                        </li>
                        <li className="mb-1">
                          <span className="font-medium">Set Clear Constraints</span>: 
                          <span className="text-gray-600 ml-1">Improves response quality by 39%</span>
                        </li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default Dashboard;