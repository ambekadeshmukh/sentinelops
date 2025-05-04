import React, { useState, useEffect } from 'react';
import { Save, AlertTriangle, Info, RefreshCw } from 'lucide-react';

// Mock API service - would be replaced with actual API client
const api = {
  getRetentionSettings: async () => {
    // This would fetch from backend
    return {
      metrics_days: 90,
      requests_days: 30,
      anomalies_days: 180,
      hallucinations_days: 90,
      raw_data_days: 7,
      aggregated_data_days: 365
    };
  },
  updateRetentionSettings: async (settings) => {
    // This would update backend
    console.log("Saving settings:", settings);
    return { success: true };
  },
  getStorageStats: async () => {
    // This would fetch actual stats from backend
    return {
      metrics_size_mb: 245.3,
      requests_size_mb: 1024.5,
      anomalies_size_mb: 32.1,
      hallucinations_size_mb: 78.2,
      raw_data_size_mb: 3512.8,
      aggregated_data_size_mb: 18.6,
      total_size_mb: 4911.5,
      estimated_monthly_cost: 98.23,
      estimated_savings: {
        metrics_days_reduction: {
          "30": 81.76,
          "60": 40.88,
          "90": 0
        },
        requests_days_reduction: {
          "7": 768.38,
          "14": 512.25,
          "30": 0
        }
      }
    };
  }
};

// DataRetentionManager component
const DataRetentionManager = () => {
  // State
  const [settings, setSettings] = useState(null);
  const [originalSettings, setOriginalSettings] = useState(null);
  const [storageStats, setStorageStats] = useState(null);
  const [saving, setSaving] = useState(false);
  const [isChanged, setIsChanged] = useState(false);
  const [estimatedSavings, setEstimatedSavings] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  // Load data on component mount
  useEffect(() => {
    loadData();
  }, []);

  // Check for changes whenever settings update
  useEffect(() => {
    if (settings && originalSettings) {
      const hasChanges = Object.keys(settings).some(key => settings[key] !== originalSettings[key]);
      setIsChanged(hasChanges);
      
      // Calculate estimated savings
      calculateEstimatedSavings();
    }
  }, [settings]);

  // Load settings and storage stats
  const loadData = async () => {
    setIsLoading(true);
    try {
      const [settingsData, statsData] = await Promise.all([
        api.getRetentionSettings(),
        api.getStorageStats()
      ]);
      
      setSettings(settingsData);
      setOriginalSettings(settingsData);
      setStorageStats(statsData);
    } catch (error) {
      console.error("Error loading data:", error);
    } finally {
      setIsLoading(false);
    }
  };

  // Calculate estimated savings based on current settings
  const calculateEstimatedSavings = () => {
    if (!settings || !originalSettings || !storageStats) return;
    
    let totalSavings = 0;
    
    // Check each data type and calculate savings
    if (settings.metrics_days < originalSettings.metrics_days) {
      // Find closest key in estimated_savings
      const keys = Object.keys(storageStats.estimated_savings.metrics_days_reduction)
        .map(Number)
        .sort((a, b) => a - b);
      
      for (const key of keys) {
        if (settings.metrics_days <= key) {
          totalSavings += storageStats.estimated_savings.metrics_days_reduction[key];
          break;
        }
      }
    }
    
    if (settings.requests_days < originalSettings.requests_days) {
      // Find closest key in estimated_savings
      const keys = Object.keys(storageStats.estimated_savings.requests_days_reduction)
        .map(Number)
        .sort((a, b) => a - b);
      
      for (const key of keys) {
        if (settings.requests_days <= key) {
          totalSavings += storageStats.estimated_savings.requests_days_reduction[key];
          break;
        }
      }
    }
    
    // For other data types, estimate based on proportion
    const dataTypes = ['anomalies', 'hallucinations', 'raw_data', 'aggregated_data'];
    dataTypes.forEach(type => {
      const daysKey = `${type}_days`;
      const sizeKey = `${type}_size_mb`;
      
      if (settings[daysKey] < originalSettings[daysKey] && storageStats[sizeKey]) {
        // Calculate proportional savings (simplified)
        const reductionRatio = 1 - (settings[daysKey] / originalSettings[daysKey]);
        const typeSavings = storageStats[sizeKey] * reductionRatio * 0.02; // $0.02 per MB is an example cost
        totalSavings += typeSavings;
      }
    });
    
    setEstimatedSavings(totalSavings);
  };

  // Handle input changes
  const handleInputChange = (key, value) => {
    // Ensure value is a number and not less than minimum allowed
    const numValue = parseInt(value);
    const validValue = !isNaN(numValue) ? Math.max(numValue, getMinimumDays(key)) : settings[key];
    
    setSettings({
      ...settings,
      [key]: validValue
    });
  };

  // Get minimum days allowed for each data type
  const getMinimumDays = (key) => {
    switch(key) {
      case 'metrics_days': return 7;
      case 'requests_days': return 1;
      case 'anomalies_days': return 7;
      case 'hallucinations_days': return 7;
      case 'raw_data_days': return 1;
      case 'aggregated_data_days': return 30;
      default: return 1;
    }
  };

  // Save settings
  const saveSettings = async () => {
    setSaving(true);
    try {
      await api.updateRetentionSettings(settings);
      setOriginalSettings(settings);
      await loadData(); // Refresh data
    } catch (error) {
      console.error("Error saving settings:", error);
    } finally {
      setSaving(false);
    }
  };

  // Format storage size
  const formatStorage = (mb) => {
    if (mb >= 1024) {
      return `${(mb / 1024).toFixed(2)} GB`;
    }
    return `${mb.toFixed(2)} MB`;
  };

  // Format cost values
  const formatCost = (value) => {
    return `$${value.toFixed(2)}`;
  };

  // Reset to original settings
  const resetSettings = () => {
    setSettings({...originalSettings});
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-semibold">Data Retention Settings</h2>
        <div className="flex space-x-2">
          <button
            className="p-2 rounded bg-gray-100 hover:bg-gray-200 text-gray-600"
            onClick={loadData}
            title="Refresh data"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>
      
      {/* Info banner */}
      <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg flex items-start">
        <Info className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5 mr-3" />
        <div>
          <p className="text-sm text-blue-800">
            Configure how long different types of monitoring data are retained. Reducing retention periods can significantly 
            decrease storage costs while still maintaining key insights. Consider your compliance requirements and 
            analytical needs when adjusting these settings.
          </p>
        </div>
      </div>
      
      {/* Settings form */}
      <div className="space-y-6">
        {/* Current storage stats */}
        <div className="bg-gray-50 p-4 rounded-lg">
          <h3 className="font-medium mb-3">Current Storage Usage</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-gray-500">Total Storage</p>
              <p className="text-lg font-semibold">{formatStorage(storageStats?.total_size_mb || 0)}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Estimated Monthly Cost</p>
              <p className="text-lg font-semibold">{formatCost(storageStats?.estimated_monthly_cost || 0)}</p>
            </div>
            {isChanged && (
              <div>
                <p className="text-sm text-gray-500">Estimated Monthly Savings</p>
                <p className="text-lg font-semibold text-green-600">{formatCost(estimatedSavings)}</p>
              </div>
            )}
          </div>
        </div>
        
        {/* Retention settings */}
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
            {/* Metrics data */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">Metrics Data</label>
              <div className="flex items-center">
                <input 
                  type="number"
                  value={settings?.metrics_days || ''}
                  onChange={(e) => handleInputChange('metrics_days', e.target.value)}
                  className="w-20 p-2 border rounded"
                  min={getMinimumDays('metrics_days')}
                />
                <span className="ml-2">days</span>
              </div>
              <p className="text-xs text-gray-500">
                Current usage: {formatStorage(storageStats?.metrics_size_mb || 0)}
              </p>
              <p className="text-xs text-gray-500">Recommended: 30-90 days</p>
            </div>
            
            {/* Request details */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">Request Details</label>
              <div className="flex items-center">
                <input 
                  type="number"
                  value={settings?.requests_days || ''}
                  onChange={(e) => handleInputChange('requests_days', e.target.value)}
                  className="w-20 p-2 border rounded"
                  min={getMinimumDays('requests_days')}
                />
                <span className="ml-2">days</span>
              </div>
              <p className="text-xs text-gray-500">
                Current usage: {formatStorage(storageStats?.requests_size_mb || 0)}
              </p>
              <p className="text-xs text-gray-500">Recommended: 7-30 days</p>
            </div>
            
            {/* Anomalies */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">Anomalies</label>
              <div className="flex items-center">
                <input 
                  type="number"
                  value={settings?.anomalies_days || ''}
                  onChange={(e) => handleInputChange('anomalies_days', e.target.value)}
                  className="w-20 p-2 border rounded"
                  min={getMinimumDays('anomalies_days')}
                />
                <span className="ml-2">days</span>
              </div>
              <p className="text-xs text-gray-500">
                Current usage: {formatStorage(storageStats?.anomalies_size_mb || 0)}
              </p>
              <p className="text-xs text-gray-500">Recommended: 30-180 days</p>
            </div>
            
            {/* Hallucinations */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">Hallucination Data</label>
              <div className="flex items-center">
                <input 
                  type="number"
                  value={settings?.hallucinations_days || ''}
                  onChange={(e) => handleInputChange('hallucinations_days', e.target.value)}
                  className="w-20 p-2 border rounded"
                  min={getMinimumDays('hallucinations_days')}
                />
                <span className="ml-2">days</span>
              </div>
              <p className="text-xs text-gray-500">
                Current usage: {formatStorage(storageStats?.hallucinations_size_mb || 0)}
              </p>
              <p className="text-xs text-gray-500">Recommended: 30-90 days</p>
            </div>
            
            {/* Raw data */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">Raw Request/Response Data</label>
              <div className="flex items-center">
                <input 
                  type="number"
                  value={settings?.raw_data_days || ''}
                  onChange={(e) => handleInputChange('raw_data_days', e.target.value)}
                  className="w-20 p-2 border rounded"
                  min={getMinimumDays('raw_data_days')}
                />
                <span className="ml-2">days</span>
              </div>
              <p className="text-xs text-gray-500">
                Current usage: {formatStorage(storageStats?.raw_data_size_mb || 0)}
              </p>
              <p className="text-xs text-gray-500">Recommended: 1-7 days</p>
            </div>
            
            {/* Aggregated data */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">Aggregated Data</label>
              <div className="flex items-center">
                <input 
                  type="number"
                  value={settings?.aggregated_data_days || ''}
                  onChange={(e) => handleInputChange('aggregated_data_days', e.target.value)}
                  className="w-20 p-2 border rounded"
                  min={getMinimumDays('aggregated_data_days')}
                />
                <span className="ml-2">days</span>
              </div>
              <p className="text-xs text-gray-500">
                Current usage: {formatStorage(storageStats?.aggregated_data_size_mb || 0)}
              </p>
              <p className="text-xs text-gray-500">Recommended: 90-365 days</p>
            </div>
          </div>
        </div>
        
        {/* Warning for significant changes */}
        {isChanged && estimatedSavings > 20 && (
          <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg flex items-start">
            <AlertTriangle className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5 mr-3" />
            <div>
              <p className="text-sm text-yellow-800">
                You're about to significantly reduce data retention, which will immediately save 
                approximately {formatCost(estimatedSavings)} per month. However, this will permanently 
                delete historical data older than the new retention periods. This action cannot be undone.
              </p>
            </div>
          </div>
        )}
        
        {/* Action buttons */}
        <div className="flex justify-end space-x-4 pt-4">
          <button
            className="px-4 py-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-50"
            onClick={resetSettings}
            disabled={!isChanged || saving}
          >
            Cancel
          </button>
          <button
            className="px-4 py-2 bg-blue-600 border border-blue-600 rounded text-white hover:bg-blue-700 flex items-center"
            onClick={saveSettings}
            disabled={!isChanged || saving}
          >
            {saving ? (
              <>
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="w-4 h-4 mr-2" />
                Save Changes
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default DataRetentionManager;