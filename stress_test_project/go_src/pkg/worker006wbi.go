
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"
)

// Status 状态类型
type Status int

const (
	StatusPending Status = iota
	StatusActive
	StatusCompleted
	StatusFailed
	StatusCancelled
)

// Config 配置结构体
type Worker006WBIConfig struct {
	Name     string `json:"name"`
	Value    int    `json:"value"`
	Enabled  bool   `json:"enabled"`
	Priority int    `json:"priority"`
}

// Worker006WBI 主结构体
type Worker006WBI struct {
	config     Worker006WBIConfig
	status     Status
	data       []map[string]interface{}
	callbacks  []func([]map[string]interface{})
	mu         sync.RWMutex
	logger     *log.Logger
}

// NewWorker006WBI 创建新实例
func NewWorker006WBI(config Worker006WBIConfig) *Worker006WBI {
	return &Worker006WBI{
		config:    config,
		status:    StatusPending,
		data:      make([]map[string]interface{}, 0),
		callbacks: make([]func([]map[string]interface{}), 0),
		logger:    log.Default(),
	}
}

// GetStatus 获取状态
func (p *Worker006WBI) GetStatus() Status {
	p.mu.RLock()
	defer p.mu.RUnlock()
	return p.status
}

// IsActive 检查是否激活
func (p *Worker006WBI) IsActive() bool {
	return p.GetStatus() == StatusActive
}

// Initialize 初始化
func (p *Worker006WBI) Initialize() error {
	p.mu.Lock()
	defer p.mu.Unlock()

	p.status = StatusActive
	p.logger.Printf("%s initialized successfully", p.config.Name)
	return nil
}

// Process 处理数据
func (p *Worker006WBI) Process(inputData []map[string]interface{}) (map[string]interface{}, error) {
	if !p.IsActive() {
		return nil, fmt.Errorf("processor is not active")
	}

	results := make([]map[string]interface{}, 0, len(inputData))
	for _, item := range inputData {
		processed := p.processItem(item)
		results = append(results, processed)
	}

	p.mu.Lock()
	p.data = append(p.data, results...)
	p.mu.Unlock()

	p.notifyCallbacks()

	return map[string]interface{}{
		"processedCount": len(results),
		"status":         "success",
	}, nil
}

// processItem 处理单个项目
func (p *Worker006WBI) processItem(item map[string]interface{}) map[string]interface{} {
	processed := make(map[string]interface{})
	for k, v := range item {
		processed[k] = v
	}
	processed["processedAt"] = time.Now().Unix()
	processed["processor"] = "Worker006WBI"
	return processed
}

// notifyCallbacks 通知回调
func (p *Worker006WBI) notifyCallbacks() {
	p.mu.RLock()
	callbacks := make([]func([]map[string]interface{}), len(p.callbacks))
	copy(callbacks, p.callbacks)
	data := make([]map[string]interface{}, len(p.data))
	copy(data, p.data)
	p.mu.RUnlock()

	for _, callback := range callbacks {
		go func(cb func([]map[string]interface{})) {
			defer func() {
				if r := recover(); r != nil {
					p.logger.Printf("Callback panic: %v", r)
				}
			}()
			cb(data)
		}(callback)
	}
}

// RegisterCallback 注册回调
func (p *Worker006WBI) RegisterCallback(callback func([]map[string]interface{})) {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.callbacks = append(p.callbacks, callback)
}

// Cleanup 清理资源
func (p *Worker006WBI) Cleanup() {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.data = make([]map[string]interface{}, 0)
	p.callbacks = make([]func([]map[string]interface{}), 0)
	p.status = StatusCompleted
}

// ExportResults 导出结果
func (p *Worker006WBI) ExportResults() (string, error) {
	p.mu.RLock()
	defer p.mu.RUnlock()
	data, err := json.MarshalIndent(p.data, "", "  ")
	return string(data), err
}

// ValidateData 验证数据
func ValidateWorker006WBIData(data map[string]interface{}) bool {
	requiredFields := []string{"id", "name", "type"}
	for _, field := range requiredFields {
		if _, exists := data[field]; !exists {
			return false
		}
	}
	return true
}

// Worker006WBIFactory 工厂
type Worker006WBIFactory struct {
	instances map[string]*Worker006WBI
	mu        sync.RWMutex
}

// NewWorker006WBIFactory 创建工厂
func NewWorker006WBIFactory() *Worker006WBIFactory {
	return &Worker006WBIFactory{
		instances: make(map[string]*Worker006WBI),
	}
}

// Create 创建实例
func (f *Worker006WBIFactory) Create(name string, config Worker006WBIConfig) *Worker006WBI {
	f.mu.Lock()
	defer f.mu.Unlock()

	if instance, exists := f.instances[name]; exists {
		return instance
	}

	instance := NewWorker006WBI(config)
	f.instances[name] = instance
	return instance
}

// GetInstance 获取实例
func (f *Worker006WBIFactory) GetInstance(name string) *Worker006WBI {
	f.mu.RLock()
	defer f.mu.RUnlock()
	return f.instances[name]
}

// RemoveInstance 移除实例
func (f *Worker006WBIFactory) RemoveInstance(name string) bool {
	f.mu.Lock()
	defer f.mu.Unlock()
	if _, exists := f.instances[name]; exists {
		delete(f.instances, name)
		return true
	}
	return false
}

func main() {
	config := Worker006WBIConfig{
		Name:     "default",
		Value:    100,
		Enabled:  true,
		Priority: 1,
	}

	processor := NewWorker006WBI(config)
	processor.Initialize()

	testData := []map[string]interface{}{
		{"id": 1, "name": "item1", "type": "test"},
		{"id": 2, "name": "item2", "type": "test"},
	}

	result, _ := processor.Process(testData)
	fmt.Printf("Result: %v\n", result)

	processor.Cleanup()
}
