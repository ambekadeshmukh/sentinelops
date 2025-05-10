import React, { useState, useEffect } from 'react';
import { 
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, 
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  Area, AreaChart
} from 'recharts';
import { RefreshCw, Download, Filter, Calendar, DollarSign, TrendingDown } from 'lucide-react';
import { axiosInstance, COLORS } from '../../App';
import LoadingSpinner from '../common/LoadingSpinner';

const CostDashboard = () => {
  // State
  const [timeRange, setTimeRange] = useState({
    start: new Date(Date.now() - 30*24*60*60*1000), // Last 30 days
    end: new Date()
  });
  const [filters, setFilters] = useState({
    provider: 'all',
    model: 'all',
    application: 'all',
    environment: 'production'
  });
  const [isLoading, setIsLoading] = useState(true);
  const [costData, setCostData] = useState(null);
  const [tokenData, setTokenData] = useState(null);
  const [costOptimization, setCostOptimization] = useState(null);
  const [modelComparison, setModelComparison] = useState(null);
  const [costBreakdown, setCostBreakdown] = useState(null);
  const [refreshInterval, setRefreshInterval] = useState(null);

  // Fetch data on component mount and when timeRange/filters change
  useEffect(() => {
    fetchDashboardData();
    
    // Setup refresh interval if active
    if (refreshInterval) {
      const interval = setInterval(fetchDashboardData, refreshInterval * 1000);
      return () => clearInterval(interval);
    }
  }, [timeRange, filters, refreshInterval]);

  // Fetch dashboard data
  const fetchDashboardData = async () => {
    setIsLoading(true);
    try {
      // Convert timeRange to ISO strings for API
      const params = {
        start_time: timeRange.start.toISOString(),
        end_time: timeRange.end.toISOString(),
        ...Object.entries(filters)
          .filter(([_, value]) => value !== 'all')
          .reduce((acc, [key, value]) => ({ ...acc, [key]: value }), {})
      };

      // Fetch cost timeseries data
      const costResponse = await axiosInstance.post('/v1/metrics/timeseries', {
        ...params,
        metrics: ['total_cost']
      });
      setCostData(costResponse.data);

      // Fetch token usage data
      const tokenResponse = await axiosInstance.post('/v1/metrics/timeseries', {
        ...params,
        metrics: ['total_tokens', 'prompt_tokens', 'completion_tokens']
      });
      setTokenData(tokenResponse.data);

      // Fetch cost optimization insights
      const optimizationResponse = await axiosInstance.get('/v1/cost/optimization', { params });
      setCostOptimization(optimizationResponse.data);

      // Fetch model comparison data
      const modelResponse = await axiosInstance.post('/v1/metrics/model-comparison', {
        ...params,
        metrics: ['cost_per_request', 'cost_per_1k_tokens', 'total_tokens_per_request']
      });
      setModelComparison(modelResponse.data);

      // Fetch cost breakdown by application and model
      const aggregateParams = {
        ...params,
        group_by: ['application', 'model', 'provider'],
        metrics: ['total_cost', 'total_tokens']
      };
      const breakdownResponse = await axiosInstance.post('/v1/metrics/aggregated', aggregateParams);
      setCostBreakdown(breakdownResponse.data);

    } catch (error) {
      console.error('Error fetching cost dashboard data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Format for currency display
  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(value);
  };

  // Format for large numbers
  const formatNumber = (num) => {
    if (num >= 1000000) return `${(num/1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num/1000).toFixed(1)}K`;
    return num.toFixed(0);
  };

  // Prepare cost time series data for chart
  const prepareCostChartData = () => {
    if (!costData || !costData.timeseries) return [];
    return costData.timeseries.labels.map((label, index) => ({
      name: label,
      cost: costData.timeseries.datasets.total_cost[index]
    }));
  };

  // Prepare token usage data for chart
  const prepareTokenChartData = () => {
    if (!tokenData || !tokenData.timeseries) return [];
    return tokenData.timeseries.labels.map((label, index) => ({
      name: label,
      total: tokenData.timeseries.datasets.total_tokens[index],
      prompt: tokenData.timeseries.datasets.prompt_tokens ? 
        tokenData.timeseries.datasets.prompt_tokens[index] : 0,
      completion: tokenData.timeseries.datasets.completion_tokens ? 
        tokenData.timeseries.datasets.completion_tokens[index] : 0
    }));
  };

  // Prepare model comparison data for chart
  const prepareModelComparisonData = () => {
    if (!modelComparison || !modelComparison.models) return [];
    
    return modelComparison.models.map((model, index) => ({
      name: `${model.provider}/${model.model}`,
      costPerRequest: modelComparison.metrics.cost_per_request[index],
      costPer1kTokens: modelComparison.metrics.cost_per_1k_tokens[index],
      tokensPerRequest: modelComparison.metrics.total_tokens_per_request[index]
    }));
  };

  // Prepare cost breakdown data for pie chart
  const prepareCostBreakdownByApp = () => {
    if (!costBreakdown || !costBreakdown.metrics) return [];
    
    // Group by application
    const appCosts = {};
    costBreakdown.metrics.forEach(metric => {
      const app = metric.application;
      if (!appCosts[app]) {
        appCosts[app] = 0;
      }
      appCosts[app] += metric.total_cost;
    });
    
    // Convert to array for chart
    return Object.entries(appCosts).map(([app, cost]) => ({
      name: app,
      value: cost
    }));
  };

  // Prepare cost breakdown data by model
  const prepareCostBreakdownByModel = () => {
    if (!costBreakdown || !costBreakdown.metrics) return [];
    
    // Group by model
    const modelCosts = {};
    costBreakdown.metrics.forEach(metric => {
      const modelKey = `${metric.provider}/${metric.model}`;
      if (!modelCosts[modelKey]) {
        modelCosts[modelKey] = 0;
      }
      modelCosts[modelKey] += metric.total_cost;
    });
    
    // Convert to array for chart
    return Object.entries(modelCosts).map(([model, cost]) => ({
      name: model,
      value: cost
    }));
  };

  // Handle filter change
  const handleFilterChange = (name, value) => {
    setFilters(prev => ({ ...prev, [name]: value }));
  };

  // Handle time range change
  const handleTimeRangeChange = (value) => {
    const now = new Date();
    let start;
    
    switch(value) {
      case "7d":
        start = new Date(now.getTime() - 7*24*60*60*1000);
        break;
      case "30d":
        start = new Date(now.getTime() - 30*24*60*60*1000);
        break;
      case "90d":
        start = new Date(now.getTime() - 90*24*60*60*1000);
        break;
      default:
        // Keep current start date
        return;
    }
    
    setTimeRange({ start, end: now });
  };

  // Calculate monthly projection based on current data
  const calculateMonthlyProjection = () => {
    if (!costData || !costData.timeseries) return 0;
    
    const totalCosts = costData.timeseries.datasets.total_cost.reduce((sum, cost) => sum + cost, 0);
    const days = Math.max(1, (timeRange.end - timeRange.start) / (24 * 60 * 60 * 1000));
    
    return (totalCosts / days) * 30; // Project to 30 days
  };

  // Calculate total cost from data
  const calculateTotalCost = () => {
    if (!costData || !costData.timeseries) return 0;
    return costData.timeseries.datasets.total_cost.reduce((sum, cost) => sum + cost, 0);
  };
  
  // Calculate total tokens from data
  const calculateTotalTokens = () => {
    if (!tokenData || !tokenData.timeseries) return 0;
    return tokenData.timeseries.datasets.total_tokens.reduce((sum, tokens) => sum + tokens, 0);
  };

  // Calculate potential savings from optimization recommendations
  const calculatePotentialSavings = () => {
    if (!costOptimization || !costOptimization.recommendations) return 0;
    return costOptimization.recommendations.reduce((sum, rec) => sum + rec.estimated_savings, 0);
  };

  // Render loading state
  if (isLoading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="p-6">
      <div className="mb-6 flex flex-col md:flex-row justify-between items-center">
        <h1 className="text-2xl font-bold mb-4 md:mb-0">Cost & Optimization Dashboard</h1>
        
        <div className="flex flex-wrap gap-2">
          {/* Time Range Selector */}
          <div className="flex items-center">
            <Calendar className="w-4 h-4 mr-2 text-gray-500" />
            <select 
              className="p-2 text-sm border rounded"
              value={
                (timeRange.end - timeRange.start) / (24*60*60*1000) === 7 ? "7d" :
                (timeRange.end - timeRange.start) / (24*60*60*1000) === 30 ? "30d" :
                (timeRange.end - timeRange.start) / (24*60*60*1000) === 90 ? "90d" : "custom"
              }
              onChange={(e) => handleTimeRangeChange(e.target.value)}
            >
              <option value="7d">Last 7 days</option>
              <option value="30d">Last 30 days</option>
              <option value="90d">Last 90 days</option>
              <option value="custom">Custom range</option>
            </select>
          </div>

          {/* Provider Filter */}
          <select 
            className="p-2 text-sm border rounded"
            value={filters.provider}
            onChange={(e) => handleFilterChange('provider', e.target.value)}
          >
            <option value="all">All Providers</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="cohere">Cohere</option>
          </select>
          
          {/* Model Filter */}
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
          
          {/* Application Filter */}
          <select 
            className="p-2 text-sm border rounded"
            value={filters.application}
            onChange={(e) => handleFilterChange('application', e.target.value)}
          >
            <option value="all">All Applications</option>
            <option value="chatbot">Chatbot</option>
            <option value="content-generator">Content Generator</option>
            <option value="customer-support">Customer Support</option>
          </select>
          
          {/* Refresh Button */}
          <button 
            className="p-2 rounded bg-gray-100 hover:bg-gray-200 flex items-center"
            onClick={fetchDashboardData}
          >
            <RefreshCw className="w-4 h-4 mr-1" />
            <span className="text-sm">Refresh</span>
          </button>
          
          {/* Export Button */}
          <button 
            className="p-2 rounded bg-gray-100 hover:bg-gray-200 flex items-center"
            onClick={() => {
              const dataStr = JSON.stringify({
                costData, 
                tokenData,
                costOptimization,
                modelComparison,
                costBreakdown
              });
              const dataUri = `data:application/json;charset=utf-8,${encodeURIComponent(dataStr)}`;
              
              const exportFileName = `sentinelops-cost-export-${new Date().toISOString()}.json`;
              
              const linkElement = document.createElement('a');
              linkElement.setAttribute('href', dataUri);
              linkElement.setAttribute('download', exportFileName);
              linkElement.click();
            }}
          >
            <Download className="w-4 h-4 mr-1" />
            <span className="text-sm">Export</span>
          </button>
        </div>
      </div>
      
      {/* Summary Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {/* Total Cost */}
        <div className="bg-white p-6 rounded-lg shadow-md">
          <div className="flex justify-between items-center mb-2">
            <h3 className="text-gray-500 text-sm">Total Cost</h3>
            <DollarSign className="w-5 h-5 text-blue-500" />
          </div>
          <div className="text-3xl font-bold">{formatCurrency(calculateTotalCost())}</div>
          <div className="text-sm text-gray-500 mt-1">
            {timeRange.start.toLocaleDateString()} - {timeRange.end.toLocaleDateString()}
          </div>
        </div>
        
        {/* Monthly Projection */}
        <div className="bg-white p-6 rounded-lg shadow-md">
          <div className="flex justify-between items-center mb-2">
            <h3 className="text-gray-500 text-sm">Monthly Projection</h3>
            <DollarSign className="w-5 h-5 text-green-500" />
          </div>
          <div className="text-3xl font-bold">{formatCurrency(calculateMonthlyProjection())}</div>
          <div className="text-sm text-gray-500 mt-1">
            Based on current usage trends
          </div>
        </div>
        
        {/* Total Tokens */}
        <div className="bg-white p-6 rounded-lg shadow-md">
          <div className="flex justify-between items-center mb-2">
            <h3 className="text-gray-500 text-sm">Total Tokens</h3>
            <Filter className="w-5 h-5 text-purple-500" />
          </div>
          <div className="text-3xl font-bold">{formatNumber(calculateTotalTokens())}</div>
          <div className="text-sm text-gray-500 mt-1">
            Avg Cost: {formatCurrency(calculateTotalCost() / Math.max(1, calculateTotalTokens() / 1000))} per 1K
          </div>
        </div>
        
        {/* Potential Savings */}
        <div className="bg-white p-6 rounded-lg shadow-md">
          <div className="flex justify-between items-center mb-2">
            <h3 className="text-gray-500 text-sm">Potential Savings</h3>
            <TrendingDown className="w-5 h-5 text-red-500" />
          </div>
          <div className="text-3xl font-bold">{formatCurrency(calculatePotentialSavings())}</div>
          <div className="text-sm text-gray-500 mt-1">
            From {costOptimization?.recommendations?.length || 0} recommendations
          </div>
        </div>
      </div>
      
      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Cost Over Time */}
        <div className="bg-white p-6 rounded-lg shadow-md">
          <h3 className="text-lg font-semibold mb-4">Cost Over Time</h3>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={prepareCostChartData()}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis tickFormatter={(value) => formatCurrency(value)} />
                <Tooltip formatter={(value) => [formatCurrency(value), 'Cost']} />
                <Area type="monotone" dataKey="cost" stroke="#8884d8" fill="#8884d8" fillOpacity={0.3} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
        
        {/* Token Usage */}
        <div className="bg-white p-6 rounded-lg shadow-md">
          <h3 className="text-lg font-semibold mb-4">Token Usage Over Time</h3>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={prepareTokenChartData()}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis tickFormatter={(value) => formatNumber(value)} />
                <Tooltip formatter={(value) => [formatNumber(value), 'Tokens']} />
                <Area type="monotone" dataKey="prompt" stackId="1" stroke="#0088FE" fill="#0088FE" fillOpacity={0.3} name="Prompt Tokens" />
                <Area type="monotone" dataKey="completion" stackId="1" stroke="#00C49F" fill="#00C49F" fillOpacity={0.3} name="Completion Tokens" />
                <Legend />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
      
      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Cost Breakdown by Application */}
        <div className="bg-white p-6 rounded-lg shadow-md">
          <h3 className="text-lg font-semibold mb-4">Cost Breakdown by Application</h3>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={prepareCostBreakdownByApp()}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                >
                  {prepareCostBreakdownByApp().map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => [formatCurrency(value), 'Cost']} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
        
        {/* Cost Breakdown by Model */}
        <div className="bg-white p-6 rounded-lg shadow-md">
          <h3 className="text-lg font-semibold mb-4">Cost Breakdown by Model</h3>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={prepareCostBreakdownByModel()}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                >
                  {prepareCostBreakdownByModel().map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => [formatCurrency(value), 'Cost']} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
      
      {/* Model Cost Comparison */}
      <div className="bg-white p-6 rounded-lg shadow-md mb-6">
        <h3 className="text-lg font-semibold mb-4">Model Cost Comparison</h3>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={prepareModelComparisonData()}
              margin={{
                top: 20, right: 30, left: 20, bottom: 5,
              }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis yAxisId="left" orientation="left" tickFormatter={(value) => formatCurrency(value)} />
              <YAxis yAxisId="right" orientation="right" tickFormatter={(value) => formatCurrency(value)} />
              <Tooltip 
                formatter={(value, name) => {
                  if (name === 'costPerRequest') return [formatCurrency(value), 'Cost per Request'];
                  if (name === 'costPer1kTokens') return [formatCurrency(value), 'Cost per 1K Tokens'];
                  return [value, name];
                }}
              />
              <Legend />
              <Bar yAxisId="left" dataKey="costPerRequest" name="Cost per Request" fill="#8884d8" />
              <Bar yAxisId="right" dataKey="costPer1kTokens" name="Cost per 1K Tokens" fill="#82ca9d" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      
      {/* Optimization Recommendations */}
      <div className="bg-white p-6 rounded-lg shadow-md">
        <h3 className="text-lg font-semibold mb-4">Optimization Recommendations</h3>
        
        {costOptimization && costOptimization.recommendations && costOptimization.recommendations.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Recommendation
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Estimated Savings
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Priority
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {costOptimization.recommendations.map((rec, index) => (
                  <tr key={index}>
                    <td className="px-6 py-4 whitespace-normal text-sm text-gray-900">
                      {rec.message}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatCurrency(rec.estimated_savings)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${
                        rec.severity === 'high' ? 'bg-red-100 text-red-800' : 
                        rec.severity === 'medium' ? 'bg-yellow-100 text-yellow-800' : 
                        'bg-green-100 text-green-800'
                      }`}>
                        {rec.severity}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-6 text-gray-500">
            No optimization recommendations available
          </div>
        )}
      </div>
    </div>
  );
};

export default CostDashboard;