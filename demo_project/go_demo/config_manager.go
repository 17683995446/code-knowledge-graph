package main

// ConfigManager - 配置管理器
// 管理应用的配置参数，支持热加载

import (
	"encoding/json"
	"fmt"
	"os"
	"sync"
	"time"
)

// AppConfig 应用配置结构体
type AppConfig struct {
	ServerHost     string            `json:"server_host"`
	ServerPort     int               `json:"server_port"`
	DatabasePath   string            `json:"database_path"`
	WatchPaths     []string          `json:"watch_paths"`
	LanguageConfig map[string]string `json:"language_config"`
	DebugMode      bool              `json:"debug_mode"`
}

// ConfigManager 配置管理器
type ConfigManager struct {
	config     AppConfig
	configPath string
	mu         sync.RWMutex
	lastLoaded time.Time
}

// NewConfigManager 创建新的配置管理器
func NewConfigManager(configPath string) *ConfigManager {
	manager := &ConfigManager{
		configPath: configPath,
	}
	return manager
}

// LoadConfig 加载配置文件
func (manager *ConfigManager) LoadConfig() error {
	manager.mu.Lock()
	defer manager.mu.Unlock()

	data, err := os.ReadFile(manager.configPath)
	if err != nil {
		return fmt.Errorf("读取配置文件失败: %w", err)
	}

	err = json.Unmarshal(data, &manager.config)
	if err != nil {
		return fmt.Errorf("解析配置文件失败: %w", err)
	}

	manager.lastLoaded = time.Now()
	return nil
}

// GetConfig 获取当前配置
func (manager *ConfigManager) GetConfig() AppConfig {
	manager.mu.RLock()
	defer manager.mu.RUnlock()
	return manager.config
}

// UpdateConfig 更新配置项
func (manager *ConfigManager) UpdateConfig(key string, value interface{}) {
	manager.mu.Lock()
	defer manager.mu.Unlock()

	configMap := make(map[string]interface{})
	data, _ := json.Marshal(manager.config)
	json.Unmarshal(data, &configMap)
	configMap[key] = value

	updatedData, _ := json.Marshal(configMap)
	json.Unmarshal(updatedData, &manager.config)
}

// GetLastLoaded 获取最后加载时间
func (manager *ConfigManager) GetLastLoaded() time.Time {
	manager.mu.RLock()
	defer manager.mu.RUnlock()
	return manager.lastLoaded
}
