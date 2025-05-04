import React, { useState, useEffect } from 'react';
import { RefreshCw, Check, Shuffle, Cloud, Database, ChartBar, Settings, Activity, AlertTriangle } from 'lucide-react';

// Mock API service - would be replaced with actual API client
const api = {
  getDeploymentStatus: async () => {
    // This would fetch from backend
    return {
      components: {
        core: {
          name: "Core Components",
          description: "Essential monitoring components",
          enabled: true,
          required: true,
          resources: {
            cpu: "0.5",
            memory: "1Gi",
            storage: "10Gi"
          }
        },
        stream_processor: {
          name: "Stream Processor",
          description: "Real-time processing of monitoring data",
          enabled: true,
          required: false,
          resources: {
            cpu: "0.5",
            memory: "2Gi",
            storage: "5Gi"
          }
        },
        advanced_analytics: {
          name: "Advanced Analytics",
          description: "Detailed metrics and trend analysis",
          enabled: false,
          required: false,
          resources: {
            cpu: "1.0",
            memory: "4Gi",
            storage: "20Gi"
          }
        },
        anomaly_detection: {
          name: "Anomaly Detection",
          description: "Automated detection of unusual patterns",
          enabled: true,
          required: false,
          resources: {
            cpu: "1.0",
            memory: "2Gi",
            storage: "10Gi"
          }
        },
        hallucination_detection: {
          name: "Hallucination Detection",
          description: "Identifies potential hallucinations in responses",
          enabled: false,
          required: false,
          resources: {
            cpu: "2.0",
            memory: "4Gi",
            storage: "10Gi"
          }
        },
        cost_optimizer: {
          name: "Cost Optimizer",
          description: "Analyzes and suggests cost-saving measures",
          enabled: false,
          required: false,
          resources: {
            cpu: "0.5",
            memory: "1Gi",
            storage: "5Gi"
          }
        },
        grafana_dashboards: {
          name: "Grafana Dashboards",
          description: "Additional visualization dashboards",
          enabled: true,
          required: false,
          resources: {
            cpu: "0.5",
            memory: "1Gi",
            storage: "1Gi"
          }
        }
      },
      cluster_status: {
        available_resources: {
          cpu: "8.0",
          memory: "16Gi",
          storage: "100Gi"
        },
        used_resources: {
          cpu: "2.5",
          memory: "6Gi",
          storage: "25Gi"
        }
      },
      current_deployment_mode: "minimal" // minimal, standard, full
    };
  },
  updateComponentStatus: async (componentId, enabled) => {
    // This would update backend
    console.log(`Setting ${componentId} to ${enabled}`);
    return { success: true };
  },
  setDeploymentMode: async (mode) => {
    // This would update backend
    console.log(`Switching to ${mode} deployment mode`);
    return { success: true };
  }
};

// Helper to parse resource strings to numbers
const parseResource = (value) => {
  if (typeof value === 'number') return value;
  
  if (typeof value !== 'string') return 0;
  
  // CPU cores
  if (value.endsWith('m')) {
    return parseFloat(value.slice(0, -1)) / 1000;
  }
  
  // Memory/Storage with Gi suffix
  if (value.endsWith('Gi')) {
    return parseFloat(value.slice(0, -2));
  }
  
  // Memory/Storage with Mi suffix
  if (value.endsWith('Mi')) {
    return parseFloat(value.slice(0, -2)) / 1024;
  }
  
  return parseFloat(value);
};

// ProgressiveScalingDeployment component
const ProgressiveScalingDeployment = () => {
  // State
  const [deploymentData, setDeploymentData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);
  const [pendingChanges, setPendingChanges] = useState({});
  
  // Load data on component mount
  useEffect(() => {
    loadData();
  }, []);
  
  // Load deployment status
  const loadData = async () => {
    setIsLoading(true);
    try {
      const data = await api.getDeploymentStatus();
      setDeploymentData(data);
      setPendingChanges({});
    } catch (error) {
      console.error("Error loading deployment status:", error);
    } finally {
      setIsLoading(false);
    }
  };
  
  // Toggle a component's enabled status
  const toggleComponent = (componentId) => {
    const component = deploymentData.components[componentId];
    
    // Don't allow toggling required components
    if (component.required) return;
    
    setPendingChanges({
      ...pendingChanges,
      [componentId]: !component.enabled
    });
  };
  
  // Apply pending changes
  const applyChanges = async () => {
    setIsUpdating(true);
    try {
      // Process each pending change
      for (const [componentId, enabled] of Object.entries(pendingChanges)) {
        await api.updateComponentStatus(componentId, enabled);
      }
      
      // Reload data to reflect changes
      await loadData();
    } catch (error) {
      console.error("Error applying changes:", error);
    } finally {
      setIsUpdating(false);
    }
  };
  
  // Change deployment mode
  const changeDeploymentMode = async (mode) => {
    setIsUpdating(true);
    try {
      await api.setDeploymentMode(mode);
      await loadData();
    } catch (error) {
      console.error("Error changing deployment mode:", error);
    } finally {
      setIsUpdating(false);
    }
  };
  
  // Check if applying changes would exceed available resources
  const checkResourceLimits = () => {
    if (!deploymentData) return { exceeded: false };
    
    const { components, cluster_status } = deploymentData;
    
    // Calculate current usage
    let totalCpu = 0;
    let totalMemory = 0;
    let totalStorage = 0;
    
    // Add up resources for components that would be enabled
    for (const [id, component] of Object.entries(components)) {
      const willBeEnabled = pendingChanges.hasOwnProperty(id) 
        ? pendingChanges[id] 
        : component.enabled;
      
      if (willBeEnabled) {
        totalCpu += parseResource(component.resources.cpu);
        totalMemory += parseResource(component.resources.memory);
        totalStorage += parseResource(component.resources.storage);
      }
    }
    
    // Check against available resources
    const availableCpu = parseResource(cluster_status.available_resources.cpu);
    const availableMemory = parseResource(cluster_status.available_resources.memory);
    const availableStorage = parseResource(cluster_status.available_resources.storage);
    
    const cpuExceeded = totalCpu > availableCpu;
    const memoryExceeded = totalMemory > availableMemory;
    const storageExceeded = totalStorage > availableStorage;
    
    return {
      exceeded: cpuExceeded || memoryExceeded || storageExceeded,
      cpuExceeded,
      memoryExceeded,
      storageExceeded,
      cpuUsage: totalCpu,
      memoryUsage: totalMemory,
      storageUsage: totalStorage,
      cpuAvailable: availableCpu,
      memoryAvailable: availableMemory,
      storageAvailable: availableStorage
    };
  };
  
  // Get component state (current or pending)
  const getComponentState = (componentId) => {
    const component = deploymentData.components[componentId];
    
    if (pendingChanges.hasOwnProperty(componentId)) {
      return pendingChanges[componentId];
    }
    
    return component.enabled;
  };
  
  // Calculate resources that would be used with pending changes
  const calculateResourceUsage = () => {
    if (!deploymentData) return { cpu: 0, memory: 0, storage: 0 };
    
    const { components } = deploymentData;
    
    let totalCpu = 0;
    let totalMemory = 0;
    let totalStorage = 0;
    
    for (const [id, component] of Object.entries(components)) {
      const willBeEnabled = pendingChanges.hasOwnProperty(id) 
        ? pendingChanges[id] 
        : component.enabled;
      
      if (willBeEnabled) {
        totalCpu += parseResource(component.resources.cpu);
        totalMemory += parseResource(component.resources.memory);
        totalStorage += parseResource(component.resources.storage);
      }
    }
    
    return { cpu: totalCpu, memory: totalMemory, storage: totalStorage };
  };
  
  // Format used/total for display
  const formatResourceUsage = (used, total, unit = "") => {
    return `${used.toFixed(1)}${unit} / ${total.toFixed(1)}${unit}`;
  };
  
  // Calculate percentage use
  const calculatePercentage = (used, total) => {
    return (used / total) * 100;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  const hasPendingChanges = Object.keys(pendingChanges).length > 0;
  const resourceStatus = checkResourceLimits();
  const currentUsage = calculateResourceUsage();

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-semibold">Progressive Scaling Deployment</h2>
        <div className="flex space-x-2">
          <button
            className="p-2 rounded bg-gray-100 hover:bg-gray-200 text-gray-600"
            onClick={loadData}
            disabled={isLoading || isUpdating}
            title="Refresh data"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>
      
      {/* Info banner */}
      <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-sm text-blue-800">
          SentinelOps supports progressive scaling, allowing you to enable only the components you need.
          Start with the minimal set and add more as your monitoring needs grow.
        </p>
      </div>
      
      {/* Current resource usage */}
      <div className="mb-6">
        <h3 className="text-base font-medium mb-3">Cluster Resource Usage</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* CPU Usage */}
          <div className="p-4 border border-gray-200 rounded-lg">
            <div className="flex justify-between items-center mb-1">
              <span className="text-sm font-medium text-gray-500">CPU</span>
              <span className="text-sm text-gray-700">
                {formatResourceUsage(currentUsage.cpu, resourceStatus.cpuAvailable, " cores")}
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2.5">
              <div 
                className={`h-2.5 rounded-full ${resourceStatus.cpuExceeded ? 'bg-red-500' : 'bg-blue-500'}`}
                style={{ width: `${Math.min(100, calculatePercentage(currentUsage.cpu, resourceStatus.cpuAvailable))}%` }}
              ></div>
            </div>
          </div>
          
          {/* Memory Usage */}
          <div className="p-4 border border-gray-200 rounded-lg">
            <div className="flex justify-between items-center mb-1">
              <span className="text-sm font-medium text-gray-500">Memory</span>
              <span className="text-sm text-gray-700">
                {formatResourceUsage(currentUsage.memory, resourceStatus.memoryAvailable, "Gi")}
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2.5">
              <div 
                className={`h-2.5 rounded-full ${resourceStatus.memoryExceeded ? 'bg-red-500' : 'bg-blue-500'}`}
                style={{ width: `${Math.min(100, calculatePercentage(currentUsage.memory, resourceStatus.memoryAvailable))}%` }}
              ></div>
            </div>
          </div>
          
          {/* Storage Usage */}
          <div className="p-4 border border-gray-200 rounded-lg">
            <div className="flex justify-between items-center mb-1">
              <span className="text-sm font-medium text-gray-500">Storage</span>
              <span className="text-sm text-gray-700">
                {formatResourceUsage(currentUsage.storage, resourceStatus.storageAvailable, "Gi")}
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2.5">
              <div 
                className={`h-2.5 rounded-full ${resourceStatus.storageExceeded ? 'bg-red-500' : 'bg-blue-500'}`}
                style={{ width: `${Math.min(100, calculatePercentage(currentUsage.storage, resourceStatus.storageAvailable))}%` }}
              ></div>
            </div>
          </div>
        </div>
      </div>
      
      {/* Resource warning if exceeded */}
      {resourceStatus.exceeded && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start">
          <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5 mr-3" />
          <div>
            <p className="text-sm text-red-800">
              The selected components would exceed your available cluster resources. 
              Please disable some components or increase your cluster resources.
            </p>
            <ul className="mt-2 text-sm text-red-800 list-disc list-inside">
              {resourceStatus.cpuExceeded && (
                <li>CPU: {formatResourceUsage(currentUsage.cpu, resourceStatus.cpuAvailable, " cores")}</li>
              )}
              {resourceStatus.memoryExceeded && (
                <li>Memory: {formatResourceUsage(currentUsage.memory, resourceStatus.memoryAvailable, "Gi")}</li>
              )}
              {resourceStatus.storageExceeded && (
                <li>Storage: {formatResourceUsage(currentUsage.storage, resourceStatus.storageAvailable, "Gi")}</li>
              )}
            </ul>
          </div>
        </div>
      )}
      
      {/* Deployment Mode Selector */}
      <div className="mb-6">
        <h3 className="text-base font-medium mb-3">Deployment Mode</h3>
        <div className="flex space-x-4">
          <button 
            className={`p-4 rounded-lg border ${deploymentData.current_deployment_mode === 'minimal' ? 'bg-blue-50 border-blue-500 text-blue-700' : 'border-gray-200 hover:bg-gray-50'} flex flex-col items-center`}
            onClick={() => changeDeploymentMode('minimal')}
            disabled={isUpdating || deploymentData.current_deployment_mode === 'minimal'}
          >
            <div className="p-2 bg-blue-100 rounded-full mb-2">
              <Settings className="w-6 h-6 text-blue-600" />
            </div>
            <span className="font-medium">Minimal</span>
            <span className="text-xs text-gray-500 mt-1">Essential monitoring only</span>
          </button>
          
          <button 
            className={`p-4 rounded-lg border ${deploymentData.current_deployment_mode === 'standard' ? 'bg-blue-50 border-blue-500 text-blue-700' : 'border-gray-200 hover:bg-gray-50'} flex flex-col items-center`}
            onClick={() => changeDeploymentMode('standard')}
            disabled={isUpdating || deploymentData.current_deployment_mode === 'standard'}
          >
            <div className="p-2 bg-blue-100 rounded-full mb-2">
              <Activity className="w-6 h-6 text-blue-600" />
            </div>
            <span className="font-medium">Standard</span>
            <span className="text-xs text-gray-500 mt-1">Balanced monitoring</span>
          </button>
          
          <button 
            className={`p-4 rounded-lg border ${deploymentData.current_deployment_mode === 'full' ? 'bg-blue-50 border-blue-500 text-blue-700' : 'border-gray-200 hover:bg-gray-50'} flex flex-col items-center`}
            onClick={() => changeDeploymentMode('full')}
            disabled={isUpdating || deploymentData.current_deployment_mode === 'full'}
          >
            <div className="p-2 bg-blue-100 rounded-full mb-2">
              <ChartBar className="w-6 h-6 text-blue-600" />
            </div>
            <span className="font-medium">Full</span>
            <span className="text-xs text-gray-500 mt-1">Comprehensive monitoring</span>
          </button>
        </div>
      </div>
      
      {/* Custom Component Selection */}
      <div className="mb-6">
        <div className="flex justify-between items-center mb-3">
          <h3 className="text-base font-medium">Component Selection</h3>
          <span className="text-sm text-gray-500">Customize which components to enable</span>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Object.entries(deploymentData.components).map(([id, component]) => (
            <div 
              key={id} 
              className={`border ${getComponentState(id) ? 'border-blue-200 bg-blue-50' : 'border-gray-200'} rounded-lg p-4 flex items-start`}
            >
              <div 
                className={`mr-4 p-2 rounded-full ${getComponentState(id) ? 'bg-blue-100' : 'bg-gray-100'}`}
              >
                {id === 'core' && <Database className={`w-5 h-5 ${getComponentState(id) ? 'text-blue-600' : 'text-gray-500'}`} />}
                {id === 'stream_processor' && <Shuffle className={`w-5 h-5 ${getComponentState(id) ? 'text-blue-600' : 'text-gray-500'}`} />}
                {id === 'advanced_analytics' && <ChartBar className={`w-5 h-5 ${getComponentState(id) ? 'text-blue-600' : 'text-gray-500'}`} />}
                {id === 'anomaly_detection' && <Activity className={`w-5 h-5 ${getComponentState(id) ? 'text-blue-600' : 'text-gray-500'}`} />}
                {id === 'hallucination_detection' && <AlertTriangle className={`w-5 h-5 ${getComponentState(id) ? 'text-blue-600' : 'text-gray-500'}`} />}
                {id === 'cost_optimizer' && <Settings className={`w-5 h-5 ${getComponentState(id) ? 'text-blue-600' : 'text-gray-500'}`} />}
                {id === 'grafana_dashboards' && <ChartBar className={`w-5 h-5 ${getComponentState(id) ? 'text-blue-600' : 'text-gray-500'}`} />}
              </div>
              
              <div className="flex-grow">
                <div className="flex justify-between items-center mb-1">
                  <h4 className="font-medium">{component.name}</h4>
                  <div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input 
                        type="checkbox" 
                        className="sr-only peer"
                        checked={getComponentState(id)}
                        onChange={() => toggleComponent(id)}
                        disabled={component.required || isUpdating}
                      />
                      <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
                    </label>
                  </div>
                </div>
                <p className="text-sm text-gray-500 mb-2">{component.description}</p>
                <div className="flex flex-wrap gap-2 text-xs">
                  <span className="px-2 py-1 bg-gray-100 rounded-full text-gray-600">
                    CPU: {component.resources.cpu}
                  </span>
                  <span className="px-2 py-1 bg-gray-100 rounded-full text-gray-600">
                    Memory: {component.resources.memory}
                  </span>
                  <span className="px-2 py-1 bg-gray-100 rounded-full text-gray-600">
                    Storage: {component.resources.storage}
                  </span>
                  {component.required && (
                    <span className="px-2 py-1 bg-blue-100 rounded-full text-blue-600">
                      Required
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
      
      {/* Action area */}
      <div className="flex justify-end">
        <button
          className="px-4 py-2 bg-blue-600 text-white rounded-lg flex items-center disabled:bg-gray-400 disabled:cursor-not-allowed"
          onClick={applyChanges}
          disabled={!hasPendingChanges || isUpdating || resourceStatus.exceeded}
        >
          {isUpdating ? (
            <>
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              Applying Changes...
            </>
          ) : (
            <>
              <Check className="w-4 h-4 mr-2" />
              Apply Changes
            </>
          )}
        </button>
      </div>
    </div>
  );
};