
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
type Worker005NVCConfig struct {
	Name     string `json:"name"`
	Value    int    `json:"value"`
	Enabled  bool   `json:"enabled"`
	Priority int    `json:"priority"`
}

// Worker005NVC 主结构体
type Worker005NVC struct {
	config     Worker005NVCConfig
	status     Status
	data       []map[string]interface{}
	callbacks  []func([]map[string]interface{})
	mu         sync.RWMutex
	logger     *log.Logger
}

// NewWorker005NVC 创建新实例
func NewWorker005NVC(config Worker005NVCConfig) *Worker005NVC {
	return &Worker005NVC{
		config:    config,
		status:    StatusPending,
		data:      make([]map[string]interface{}, 0),
		callbacks: make([]func([]map[string]interface{}), 0),
		logger:    log.Default(),
	}
}

// GetStatus 获取状态
func (p *Worker005NVC) GetStatus() Status {
	p.mu.RLock()
	defer p.mu.RUnlock()
	return p.status
}

// IsActive 检查是否激活
func (p *Worker005NVC) IsActive() bool {
	return p.GetStatus() == StatusActive
}

// Initialize 初始化
func (p *Worker005NVC) Initialize() error {
	p.mu.Lock()
	defer p.mu.Unlock()

	p.status = StatusActive
	p.logger.Printf("%s initialized successfully", p.config.Name)
	return nil
}

// Process 处理数据
func (p *Worker005NVC) Process(inputData []map[string]interface{}) (map[string]interface{}, error) {
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
func (p *Worker005NVC) processItem(item map[string]interface{}) map[string]interface{} {
	processed := make(map[string]interface{})
	for k, v := range item {
		processed[k] = v
	}
	processed["processedAt"] = time.Now().Unix()
	processed["processor"] = "Worker005NVC"
	return processed
}

// notifyCallbacks 通知回调
func (p *Worker005NVC) notifyCallbacks() {
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
func (p *Worker005NVC) RegisterCallback(callback func([]map[string]interface{})) {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.callbacks = append(p.callbacks, callback)
}

// Cleanup 清理资源
func (p *Worker005NVC) Cleanup() {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.data = make([]map[string]interface{}, 0)
	p.callbacks = make([]func([]map[string]interface{}), 0)
	p.status = StatusCompleted
}

// ExportResults 导出结果
func (p *Worker005NVC) ExportResults() (string, error) {
	p.mu.RLock()
	defer p.mu.RUnlock()
	data, err := json.MarshalIndent(p.data, "", "  ")
	return string(data), err
}

// ValidateData 验证数据
func ValidateWorker005NVCData(data map[string]interface{}) bool {
	requiredFields := []string{"id", "name", "type"}
	for _, field := range requiredFields {
		if _, exists := data[field]; !exists {
			return false
		}
	}
	return true
}

// Worker005NVCFactory 工厂
type Worker005NVCFactory struct {
	instances map[string]*Worker005NVC
	mu        sync.RWMutex
}

// NewWorker005NVCFactory 创建工厂
func NewWorker005NVCFactory() *Worker005NVCFactory {
	return &Worker005NVCFactory{
		instances: make(map[string]*Worker005NVC),
	}
}

// Create 创建实例
func (f *Worker005NVCFactory) Create(name string, config Worker005NVCConfig) *Worker005NVC {
	f.mu.Lock()
	defer f.mu.Unlock()

	if instance, exists := f.instances[name]; exists {
		return instance
	}

	instance := NewWorker005NVC(config)
	f.instances[name] = instance
	return instance
}

// GetInstance 获取实例
func (f *Worker005NVCFactory) GetInstance(name string) *Worker005NVC {
	f.mu.RLock()
	defer f.mu.RUnlock()
	return f.instances[name]
}

// RemoveInstance 移除实例
func (f *Worker005NVCFactory) RemoveInstance(name string) bool {
	f.mu.Lock()
	defer f.mu.Unlock()
	if _, exists := f.instances[name]; exists {
		delete(f.instances, name)
		return true
	}
	return false
}

func main() {
	config := Worker005NVCConfig{
		Name:     "default",
		Value:    100,
		Enabled:  true,
		Priority: 1,
	}

	processor := NewWorker005NVC(config)
	processor.Initialize()

	testData := []map[string]interface{}{
		{"id": 1, "name": "item1", "type": "test"},
		{"id": 2, "name": "item2", "type": "test"},
	}

	result, _ := processor.Process(testData)
	fmt.Printf("Result: %v\n", result)

	processor.Cleanup()
}
