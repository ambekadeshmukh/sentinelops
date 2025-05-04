import React, { useState, useEffect } from 'react';
import { Save, HelpCircle, RefreshCw, AlertTriangle, BarChart } from 'lucide-react';

// Mock API service - would be replaced with actual API client
const api = {
  getSamplingSettings: async () => {
    // This would fetch from backend
    return {
      enabled: false,
      rate: 100, // 100% = no sampling
      applications: [
        {
          name: 'chatbot',
          enabled: true,
          rate: 100,
          request_count_past_day: 12432
        },
        {
          name: 'content-generator',
          enabled: false,
          rate: 50,
          request_count_past_day: 8753
        },
        {
          name: 'customer-support',
          enabled: false,
          rate: 25,
          request_count_past_day: 5218
        },
        {
          name: 'research-assistant',
          enabled: false,
          rate: 10,
          request_count_past_day: 874
        }
      ],
      models: [
        {
          name: 'gpt-4',
          provider: 'openai',
          enabled: false,
          rate: 100,
          request_count_past_day: 4289
        },
        {
          name: 'gpt-3.5-turbo',
          provider: 'openai',
          enabled: false,
          rate: 25,
          request_count_past_day: 18904
        },
        {
          name: 'claude-2',
          provider: 'anthropic',
          enabled: false,
          rate: 50,
          request_count_past_day: 3218
        }
      ],
      anomaly_detection_impact: {
        performance_degradation: 0, // 0-100%
        error_detection_loss: 0,
        hallucination_detection_loss: 0,
        cost_optimization_impact: 0
      }
    };
  },
  updateSamplingSettings: async (settings) => {
    // This would update backend
    console.log("Saving settings:", settings);
    return { success: true };
  },
  getImpactEstimate: async (settings) => {
    // This would calculate the impact of new settings
    // Here we simulate calculation based on sampling rates
    
    // Default is no impact (100% sampling)
    let performance = 0;
    let error_detection = 0;
    let hallucination_detection = 0;
    let cost_reduction = 0;
    
    // Global sampling impact
    if (settings.enabled) {
      const globalRate = settings.rate;
      performance = Math.max(0, Math.min(50, 100 - globalRate));
      error_detection = Math.max(0, Math.min(60, 100 - globalRate));
      hallucination_detection = Math.max(0, Math.min(70, 100 - globalRate));
      cost_reduction = 100 - globalRate;
    }
    
    // Additional impacts from application-specific sampling
    const enabledApps = settings.applications.filter(app => app.enabled);
    if (enabledApps.length > 0) {
      const appImpact = enabledApps.reduce((sum, app) => sum + (100 - app.rate), 0) / enabledApps.length;
      performance = Math.max(performance, appImpact * 0.3);
      error_detection = Math.max(error_detection, appImpact * 0.4);
      hallucination_detection = Math.max(hallucination_detection, appImpact * 0.5);
      cost_reduction = Math.max(cost_reduction, appImpact * 0.7);
    }
    
    // Additional impacts from model-specific sampling
    const enabledModels = settings.models.filter(model => model.enabled);
    if (enabledModels.length > 0) {
      const modelImpact = enabledModels.reduce((sum, model) => sum + (100 - model.rate), 0) / enabledModels.length;
      performance = Math.max(performance, modelImpact * 0.2);
      error_detection = Math.max(error_detection, modelImpact * 0.3);
      hallucination_detection = Math.max(hallucination_detection, modelImpact * 0.4);
      cost_reduction = Math.max(cost_reduction, modelImpact * 0.8);
    }
    
    return {
      performance_degradation: Math.min(100, Math.round(performance)),
      error_detection_loss: Math.min(100, Math.round(error_detection)),
      hallucination_detection_loss: Math.min(100, Math.round(hallucination_detection)),
      cost_optimization_impact: Math.min(100, Math.round(cost_reduction))
    };
  }
};

// DataSamplingManager component
const DataSamplingManager = () => {
  // State
  const [settings, setSettings] = useState(null);
  const [originalSettings, setOriginalSettings] = useState(null);
  const [saving, setSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [impact, setImpact] = useState(null);
  const [isChanged, setIsChanged] = useState(false);
  const [showHelp, setShowHelp] = useState(false);

  // Load data on component mount
  useEffect(() => {
    loadData();
  }, []);

  // Calculate impact when settings change
  useEffect(() => {
    if (settings && originalSettings) {
      const hasChanges = JSON.stringify(settings) !== JSON.stringify(originalSettings);
      setIsChanged(hasChanges);
      
      if (hasChanges) {
        calculateImpact();
      } else {
        setImpact(settings.anomaly_detection_impact);
      }
    }
  }, [settings]);

  // Load settings from API
  const loadData = async () => {
    setIsLoading(true);
    try {
      const data = await api.getSamplingSettings();
      setSettings(data);
      setOriginalSettings(data);
      setImpact(data.anomaly_detection_impact);
    } catch (error) {
      console.error("Error loading data:", error);
    } finally {
      setIsLoading(false);
    }
  };

  // Calculate the impact of current settings
  const calculateImpact = async () => {
    try {
      const impactData = await api.getImpactEstimate(settings);
      setImpact(impactData);
    } catch (error) {
      console.error("Error calculating impact:", error);
    }
  };

  // Toggle global sampling
  const toggleGlobalSampling = () => {
    setSettings({
      ...settings,
      enabled: !settings.enabled
    });
  };

  // Update global sampling rate
  const updateGlobalRate = (rate) => {
    const numRate = parseInt(rate);
    if (!isNaN(numRate) && numRate >= 1 && numRate <= 100) {
      setSettings({
        ...settings,
        rate: numRate
      });
    }
  };

  // Toggle application sampling
  const toggleApplicationSampling = (index) => {
    const newApplications = [...settings.applications];
    newApplications[index].enabled = !newApplications[index].enabled;
    
    setSettings({
      ...settings,
      applications: newApplications
    });
  };

  // Update application sampling rate
  const updateApplicationRate = (index, rate) => {
    const numRate = parseInt(rate);
    if (!isNaN(numRate) && numRate >= 1 && numRate <= 100) {
      const newApplications = [...settings.applications];
      newApplications[index].rate = numRate;
      
      setSettings({
        ...settings,
        applications: newApplications
      });
    }
  };

  // Toggle model sampling
  const toggleModelSampling = (index) => {
    const newModels = [...settings.models];
    newModels[index].enabled = !newModels[index].enabled;
    
    setSettings({
      ...settings,
      models: newModels
    });
  };

  // Update model sampling rate
  const updateModelRate = (index, rate) => {
    const numRate = parseInt(rate);
    if (!isNaN(numRate) && numRate >= 1 && numRate <= 100) {
      const newModels = [...settings.models];
      newModels[index].rate = numRate;
      
      setSettings({
        ...settings,
        models: newModels
      });
    }
  };

  // Save settings
  const saveSettings = async () => {
    setSaving(true);
    try {
      await api.updateSamplingSettings(settings);
      setOriginalSettings(settings);
      await loadData();
    } catch (error) {
      console.error("Error saving settings:", error);
    } finally {
      setSaving(false);
    }
  };

  // Reset settings to original
  const resetSettings = () => {
    setSettings({...originalSettings});
  };

  // Format request count
  const formatNumber = (num) => {
    if (num === null || num === undefined) return '-';
    if (num >= 1000000) return `${(num/1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num/1000).toFixed(1)}K`;
    return num.toString();
  };

  // Determine impact level style
  const getImpactLevel = (value) => {
    if (value <= 5) return { color: 'text-green-600', label: 'Minimal' };
    if (value <= 15) return { color: 'text-green-500', label: 'Low' };
    if (value <= 30) return { color: 'text-yellow-500', label: 'Moderate' };
    if (value <= 50) return { color: 'text-orange-500', label: 'Significant' };
    return { color: 'text-red-500', label: 'High' };
  };

  // Help content
  const helpContent = (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
      <h3 className="text-blue-800 font-medium mb-2">About Data Sampling</h3>
      <p className="text-sm text-blue-800 mb-2">
        Data sampling reduces the volume of monitored requests by only processing a percentage of them. This can significantly 
        reduce data storage and processing costs, especially for high-volume applications.
      </p>
      <ul className="text-sm text-blue-800 list-disc list-inside space-y-1">
        <li><span className="font-medium">Global Sampling</span>: Applies to all requests uniformly</li>
        <li><span className="font-medium">Application-specific</span>: Sample different apps at different rates</li>
        <li><span className="font-medium">Model-specific</span>: Apply different rates to different LLM models</li>
      </ul>
      <p className="text-sm text-blue-800 mt-2">
        <span className="font-medium">Important:</span> Higher sampling rates (e.g., 100%) provide more accurate monitoring but higher costs.
        Lower rates (e.g., 10%) reduce costs but may miss infrequent anomalies.
      </p>
    </div>
  );

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
        <div className="flex items-center">
          <h2 className="text-xl font-semibold">Data Sampling Configuration</h2>
          <button
            className="ml-2 text-gray-400 hover:text-gray-600"
            onClick={() => setShowHelp(!showHelp)}
          >
            <HelpCircle className="w-5 h-5" />
          </button>
        </div>
        
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
      
      {/* Help content */}
      {showHelp && helpContent}
      
      <div className="space-y-8">
        {/* Impact summary */}
        <div className="bg-gray-50 p-4 rounded-lg">
          <h3 className="font-medium mb-3 flex items-center">
            <BarChart className="w-4 h-4 mr-2" />
            Impact of Current Sampling Configuration
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <p className="text-sm text-gray-500">Performance Impact</p>
              <p className={`text-lg font-semibold ${getImpactLevel(impact?.performance_degradation || 0).color}`}>
                {getImpactLevel(impact?.performance_degradation || 0).label} 
                <span className="text-sm ml-1">({impact?.performance_degradation || 0}%)</span>
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Error Detection Impact</p>
              <p className={`text-lg font-semibold ${getImpactLevel(impact?.error_detection_loss || 0).color}`}>
                {getImpactLevel(impact?.error_detection_loss || 0).label}
                <span className="text-sm ml-1">({impact?.error_detection_loss || 0}%)</span>
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Hallucination Detection Impact</p>
              <p className={`text-lg font-semibold ${getImpactLevel(impact?.hallucination_detection_loss || 0).color}`}>
                {getImpactLevel(impact?.hallucination_detection_loss || 0).label}
                <span className="text-sm ml-1">({impact?.hallucination_detection_loss || 0}%)</span>
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Cost Optimization</p>
              <p className="text-lg font-semibold text-green-600">
                {impact?.cost_optimization_impact || 0}% Reduction
              </p>
            </div>
          </div>
        </div>
        
        {/* Global sampling */}
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <div className="bg-gray-50 p-4 border-b border-gray-200 flex justify-between items-center">
            <h3 className="font-medium">Global Sampling</h3>
            <label className="relative inline-flex items-center cursor-pointer">
              <input 
                type="checkbox" 
                className="sr-only peer"
                checked={settings?.enabled}
                onChange={toggleGlobalSampling}
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>
          
          <div className={`p-4 space-y-4 ${settings?.enabled ? '' : 'opacity-50'}`}>
            <div className="flex items-center space-x-4">
              <label className="text-sm font-medium text-gray-700 min-w-32">Sampling Rate:</label>
              <div className="flex items-center space-x-2">
                <input 
                  type="range"
                  min="1"
                  max="100"
                  value={settings?.rate || 100}
                  onChange={(e) => updateGlobalRate(e.target.value)}
                  disabled={!settings?.enabled}
                  className="w-40"
                />
                <div className="w-14 text-center">
                  <span className="text-sm font-medium">{settings?.rate || 100}%</span>
                </div>
              </div>
            </div>
            
            <p className="text-sm text-gray-500">
              This will sample {settings?.rate || 100}% of all requests across all applications and models.
            </p>
          </div>
        </div>
        
        {/* Application-specific sampling */}
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <div className="bg-gray-50 p-4 border-b border-gray-200">
            <h3 className="font-medium">Application-Specific Sampling</h3>
          </div>
          
          <div className="p-4">
            <table className="min-w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="py-2 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Application</th>
                  <th className="py-2 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Request Volume</th>
                  <th className="py-2 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Enabled</th>
                  <th className="py-2 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Sampling Rate</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {settings?.applications.map((app, index) => (
                  <tr key={index}>
                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="font-medium text-gray-900">{app.name}</div>
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">{formatNumber(app.request_count_past_day)}/day</div>
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input 
                          type="checkbox" 
                          className="sr-only peer"
                          checked={app.enabled}
                          onChange={() => toggleApplicationSampling(index)}
                          disabled={!settings.enabled}
                        />
                        <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
                      </label>
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="flex items-center space-x-2">
                        <input 
                          type="range"
                          min="1"
                          max="100"
                          value={app.rate}
                          onChange={(e) => updateApplicationRate(index, e.target.value)}
                          disabled={!settings.enabled || !app.enabled}
                          className="w-32"
                        />
                        <div className="w-12 text-center">
                          <span className="text-sm font-medium">{app.rate}%</span>
                        </div>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        
        {/* Model-specific sampling */}
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <div className="bg-gray-50 p-4 border-b border-gray-200">
            <h3 className="font-medium">Model-Specific Sampling</h3>
          </div>
          
          <div className="p-4">
            <table className="min-w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="py-2 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Model</th>
                  <th className="py-2 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Provider</th>
                  <th className="py-2 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Request Volume</th>
                  <th className="py-2 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Enabled</th>
                  <th className="py-2 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Sampling Rate</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {settings?.models.map((model, index) => (
                  <tr key={index}>
                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="font-medium text-gray-900">{model.name}</div>
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">{model.provider}</div>
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">{formatNumber(model.request_count_past_day)}/day</div>
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input 
                          type="checkbox" 
                          className="sr-only peer"
                          checked={model.enabled}
                          onChange={() => toggleModelSampling(index)}
                          disabled={!settings.enabled}
                        />
                        <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
                      </label>
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="flex items-center space-x-2">
                        <input 
                          type="range"
                          min="1"
                          max="100"
                          value={model.rate}
                          onChange={(e) => updateModelRate(index, e.target.value)}
                          disabled={!settings.enabled || !model.enabled}
                          className="w-32"
                        />
                        <div className="w-12 text-center">
                          <span className="text-sm font-medium">{model.rate}%</span>
                        </div>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        
        {/* Warning for significant changes */}
        {isChanged && impact && (impact.error_detection_loss > 30 || impact.hallucination_detection_loss > 30) && (
          <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg flex items-start">
            <AlertTriangle className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5 mr-3" />
            <div>
              <p className="text-sm text-yellow-800">
                Your sampling configuration may significantly impact detection capabilities. With these settings, you
                could miss up to {Math.max(impact.error_detection_loss, impact.hallucination_detection_loss)}% of 
                potential issues while reducing costs by {impact.cost_optimization_impact}%. Consider using a higher
                sampling rate for critical applications.
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