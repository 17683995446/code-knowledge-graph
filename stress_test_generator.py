#!/usr/bin/env python3
"""
Stress Test Generator - 压力测试文件生成器
生成大量代码文件用于测试知识图谱系统的处理能力
"""

import os
import random
import string
import time

BASE_DIR = "/workspace/code_knowledge_graph/stress_test_project"

# Python类模板
PYTHON_CLASS_TEMPLATE = '''
"""
Module: {module_name}
Description: {description}
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class {class_name}Status(Enum):
    """状态枚举"""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class {class_name}Config:
    """配置数据类"""
    name: str
    value: int
    enabled: bool = True
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {{
            "name": self.name,
            "value": self.value,
            "enabled": self.enabled,
            "priority": self.priority
        }}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "{class_name}Config":
        return cls(
            name=data.get("name", ""),
            value=data.get("value", 0),
            enabled=data.get("enabled", True),
            priority=data.get("priority", 0)
        )


class {class_name}:
    """
    {class_name} - {description}
    """

    def __init__(self, config: Optional[{class_name}Config] = None):
        self.config = config or {class_name}Config(name="default", value=0)
        self._status = {class_name}Status.PENDING
        self._data: List[Dict[str, Any]] = []
        self._callbacks: List[callable] = []

    @property
    def status(self) -> {class_name}Status:
        return self._status

    @property
    def is_active(self) -> bool:
        return self._status == {class_name}Status.ACTIVE

    def initialize(self) -> bool:
        """初始化"""
        try:
            self._status = {class_name}Status.ACTIVE
            logger.info(f"{{self.__class__.__name__}} initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Initialization failed: {{e}}")
            self._status = {class_name}Status.FAILED
            return False

    def process(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """处理数据"""
        if not self.is_active:
            raise RuntimeError("Processor is not active")

        results = []
        for item in data:
            processed = self._process_item(item)
            results.append(processed)

        self._data.extend(results)
        self._notify_callbacks()

        return {{
            "processed_count": len(results),
            "status": "success"
        }}

    def _process_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """处理单个项目"""
        return {{
            **item,
            "processed_at": time.time(),
            "processor": self.__class__.__name__
        }}

    def _notify_callbacks(self):
        """通知回调"""
        for callback in self._callbacks:
            try:
                callback(self._data)
            except Exception as e:
                logger.warning(f"Callback failed: {{e}}")

    def register_callback(self, callback: callable):
        """注册回调"""
        self._callbacks.append(callback)

    def cleanup(self):
        """清理资源"""
        self._data.clear()
        self._callbacks.clear()
        self._status = {class_name}Status.COMPLETED

    def export_results(self, filepath: str):
        """导出结果"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def validate_data(data: Dict[str, Any]) -> bool:
        """验证数据"""
        required_fields = ["id", "name", "type"]
        return all(field in data for field in required_fields)


class {class_name}Factory:
    """工厂类"""

    _instances: Dict[str, {class_name}] = {{}}

    @classmethod
    def create(cls, name: str, config: Optional[{class_name}Config] = None) -> {class_name}:
        if name in cls._instances:
            return cls._instances[name]

        instance = {class_name}(config)
        cls._instances[name] = instance
        return instance

    @classmethod
    def get_instance(cls, name: str) -> Optional[{class_name}]:
        return cls._instances.get(name)

    @classmethod
    def remove_instance(cls, name: str) -> bool:
        if name in cls._instances:
            del cls._instances[name]
            return True
        return False

    @classmethod
    def clear_all(cls):
        cls._instances.clear()


def create_default_{var_name}() -> {class_name}:
    """创建默认实例"""
    config = {class_name}Config(name="default", value=100, priority=1)
    return {class_name}Factory.create("default", config)


def main():
    """主函数"""
    processor = create_default_{var_name}()
    processor.initialize()

    test_data = [
        {{"id": 1, "name": "item1", "type": "test"}},
        {{"id": 2, "name": "item2", "type": "test"}},
        {{"id": 3, "name": "item3", "type": "test"}},
    ]

    result = processor.process(test_data)
    print(f"Processing result: {{result}}")

    processor.cleanup()


if __name__ == "__main__":
    main()
'''

# JavaScript类模板
JS_CLASS_TEMPLATE = '''
/**
 * {module_name} - {description}
 * @module {module_name}
 */

/**
 * 状态枚举
 * @enum {{string}}
 */
const {class_name}Status = {{
    PENDING: 'pending',
    ACTIVE: 'active',
    COMPLETED: 'completed',
    FAILED: 'failed',
    CANCELLED: 'cancelled'
}};

/**
 * 默认配置
 * @type {{Object}}
 */
const DEFAULT_CONFIG = {{
    name: 'default',
    value: 0,
    enabled: true,
    priority: 0
}};

/**
 * {class_name}类
 * @class
 */
class {class_name} {{
    /**
     * 构造函数
     * @param {{Object}} config - 配置对象
     */
    constructor(config = DEFAULT_CONFIG) {{
        this.config = {{ ...DEFAULT_CONFIG, ...config }};
        this._status = {class_name}Status.PENDING;
        this._data = [];
        this._callbacks = [];
    }}

    /**
     * 获取状态
     * @returns {{string}} 当前状态
     */
    get status() {{
        return this._status;
    }}

    /**
     * 检查是否激活
     * @returns {{boolean}}
     */
    isActive() {{
        return this._status === {class_name}Status.ACTIVE;
    }}

    /**
     * 初始化
     * @returns {{boolean}} 是否成功
     */
    initialize() {{
        try {{
            this._status = {class_name}Status.ACTIVE;
            console.log(`${{this.constructor.name}} initialized`);
            return true;
        }} catch (error) {{
            console.error('Initialization failed:', error);
            this._status = {class_name}Status.FAILED;
            return false;
        }}
    }}

    /**
     * 处理数据
     * @param {{Array}} data - 输入数据
     * @returns {{Object}} 处理结果
     */
    process(data) {{
        if (!this.isActive()) {{
            throw new Error('Processor is not active');
        }}

        const results = data.map(item => this._processItem(item));
        this._data.push(...results);
        this._notifyCallbacks();

        return {{
            processedCount: results.length,
            status: 'success'
        }};
    }}

    /**
     * 处理单个项目
     * @private
     * @param {{Object}} item - 数据项
     * @returns {{Object}} 处理后的数据
     */
    _processItem(item) {{
        return {{
            ...item,
            processedAt: Date.now(),
            processor: this.constructor.name
        }};
    }}

    /**
     * 通知回调
     * @private
     */
    _notifyCallbacks() {{
        this._callbacks.forEach(callback => {{
            try {{
                callback(this._data);
            }} catch (error) {{
                console.warn('Callback failed:', error);
            }}
        }});
    }}

    /**
     * 注册回调
     * @param {{Function}} callback - 回调函数
     */
    registerCallback(callback) {{
        this._callbacks.push(callback);
    }}

    /**
     * 清理资源
     */
    cleanup() {{
        this._data = [];
        this._callbacks = [];
        this._status = {class_name}Status.COMPLETED;
    }}

    /**
     * 导出结果
     * @returns {{Object}} JSON数据
     */
    exportResults() {{
        return JSON.stringify(this._data, null, 2);
    }}

    /**
     * 验证数据
     * @static
     * @param {{Object}} data - 待验证数据
     * @returns {{boolean}}
     */
    static validateData(data) {{
        const requiredFields = ['id', 'name', 'type'];
        return requiredFields.every(field => field in data);
    }}
}}

/**
 * 工厂类
 */
class {class_name}Factory {{
    static _instances = new Map();

    static create(name, config = null) {{
        if (this._instances.has(name)) {{
            return this._instances.get(name);
        }}

        const instance = new {class_name}(config);
        this._instances.set(name, instance);
        return instance;
    }}

    static getInstance(name) {{
        return this._instances.get(name);
    }}

    static removeInstance(name) {{
        return this._instances.delete(name);
    }}

    static clearAll() {{
        this._instances.clear();
    }}
}}

/**
 * 创建默认实例
 * @returns {{{class_name}}}
 */
function createDefault{class_name}() {{
    const config = {{ name: 'default', value: 100, priority: 1 }};
    return {class_name}Factory.create('default', config);
}}

export {{ {class_name}, {class_name}Factory, {class_name}Status, createDefault{class_name} }};
'''

# Java类模板
JAVA_CLASS_TEMPLATE = '''
package com.stress.test;

import java.util.*;
import java.util.logging.Logger;
import java.util.stream.Collectors;

/**
 * {class_name} - {description}
 */
public class {class_name} {{

    private static final Logger logger = Logger.getLogger({class_name}.class.getName());

    /**
     * 状态枚举
     */
    public enum Status {{
        PENDING, ACTIVE, COMPLETED, FAILED, CANCELLED
    }}

    /**
     * 配置类
     */
    public static class Config {{
        private final String name;
        private final int value;
        private boolean enabled;
        private int priority;

        public Config(String name, int value) {{
            this.name = name;
            this.value = value;
            this.enabled = true;
            this.priority = 0;
        }}

        public String getName() {{ return name; }}
        public int getValue() {{ return value; }}
        public boolean isEnabled() {{ return enabled; }}
        public void setEnabled(boolean enabled) {{ this.enabled = enabled; }}
        public int getPriority() {{ return priority; }}
        public void setPriority(int priority) {{ this.priority = priority; }}

        public Map<String, Object> toMap() {{
            Map<String, Object> map = new HashMap<>();
            map.put("name", name);
            map.put("value", value);
            map.put("enabled", enabled);
            map.put("priority", priority);
            return map;
        }}
    }}

    private final Config config;
    private Status status;
    private final List<Map<String, Object>> data;
    private final List<Consumer<List<Map<String, Object>>>> callbacks;

    /**
     * 构造函数
     */
    public {class_name}(Config config) {{
        this.config = config != null ? config : new Config("default", 0);
        this.status = Status.PENDING;
        this.data = new ArrayList<>();
        this.callbacks = new ArrayList<>();
    }}

    /**
     * 获取状态
     */
    public Status getStatus() {{
        return status;
    }}

    /**
     * 检查是否激活
     */
    public boolean isActive() {{
        return status == Status.ACTIVE;
    }}

    /**
     * 初始化
     */
    public boolean initialize() {{
        try {{
            status = Status.ACTIVE;
            logger.info(getClass().getSimpleName() + " initialized successfully");
            return true;
        }} catch (Exception e) {{
            logger.severe("Initialization failed: " + e.getMessage());
            status = Status.FAILED;
            return false;
        }}
    }}

    /**
     * 处理数据
     */
    public Map<String, Object> process(List<Map<String, Object>> inputData) {{
        if (!isActive()) {{
            throw new IllegalStateException("Processor is not active");
        }}

        List<Map<String, Object>> results = inputData.stream()
            .map(this::processItem)
            .collect(Collectors.toList());

        data.addAll(results);
        notifyCallbacks();

        Map<String, Object> result = new HashMap<>();
        result.put("processedCount", results.size());
        result.put("status", "success");
        return result;
    }}

    /**
     * 处理单个项目
     */
    private Map<String, Object> processItem(Map<String, Object> item) {{
        Map<String, Object> processed = new HashMap<>(item);
        processed.put("processedAt", System.currentTimeMillis());
        processed.put("processor", getClass().getSimpleName());
        return processed;
    }}

    /**
     * 通知回调
     */
    private void notifyCallbacks() {{
        for (Consumer<List<Map<String, Object>>> callback : callbacks) {{
            try {{
                callback.accept(new ArrayList<>(data));
            }} catch (Exception e) {{
                logger.warning("Callback failed: " + e.getMessage());
            }}
        }}
    }}

    /**
     * 注册回调
     */
    public void registerCallback(Consumer<List<Map<String, Object>>> callback) {{
        callbacks.add(callback);
    }}

    /**
     * 清理资源
     */
    public void cleanup() {{
        data.clear();
        callbacks.clear();
        status = Status.COMPLETED;
    }}

    /**
     * 验证数据
     */
    public static boolean validateData(Map<String, Object> data) {{
        String[] requiredFields = {{"id", "name", "type"}};
        return Arrays.stream(requiredFields)
            .allMatch(field -> data.containsKey(field));
    }}
}}

/**
 * 消费者接口
 */
@FunctionalInterface
interface Consumer<T> {{
    void accept(T t);
}}
'''

# Go文件模板
GO_FILE_TEMPLATE = '''
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
type {struct_name}Config struct {{
	Name     string `json:"name"`
	Value    int    `json:"value"`
	Enabled  bool   `json:"enabled"`
	Priority int    `json:"priority"`
}}

// {struct_name} 主结构体
type {struct_name} struct {{
	config     {struct_name}Config
	status     Status
	data       []map[string]interface{{}}
	callbacks  []func([]map[string]interface{{}})
	mu         sync.RWMutex
	logger     *log.Logger
}}

// New{struct_name} 创建新实例
func New{struct_name}(config {struct_name}Config) *{struct_name} {{
	return &{struct_name}{{
		config:    config,
		status:    StatusPending,
		data:      make([]map[string]interface{{}}, 0),
		callbacks: make([]func([]map[string]interface{{}}), 0),
		logger:    log.Default(),
	}}
}}

// GetStatus 获取状态
func (p *{struct_name}) GetStatus() Status {{
	p.mu.RLock()
	defer p.mu.RUnlock()
	return p.status
}}

// IsActive 检查是否激活
func (p *{struct_name}) IsActive() bool {{
	return p.GetStatus() == StatusActive
}}

// Initialize 初始化
func (p *{struct_name}) Initialize() error {{
	p.mu.Lock()
	defer p.mu.Unlock()

	p.status = StatusActive
	p.logger.Printf("%s initialized successfully", p.config.Name)
	return nil
}}

// Process 处理数据
func (p *{struct_name}) Process(inputData []map[string]interface{{}}) (map[string]interface{{}}, error) {{
	if !p.IsActive() {{
		return nil, fmt.Errorf("processor is not active")
	}}

	results := make([]map[string]interface{{}}, 0, len(inputData))
	for _, item := range inputData {{
		processed := p.processItem(item)
		results = append(results, processed)
	}}

	p.mu.Lock()
	p.data = append(p.data, results...)
	p.mu.Unlock()

	p.notifyCallbacks()

	return map[string]interface{{}}{{
		"processedCount": len(results),
		"status":         "success",
	}}, nil
}}

// processItem 处理单个项目
func (p *{struct_name}) processItem(item map[string]interface{{}}) map[string]interface{{}} {{
	processed := make(map[string]interface{{}})
	for k, v := range item {{
		processed[k] = v
	}}
	processed["processedAt"] = time.Now().Unix()
	processed["processor"] = "{struct_name}"
	return processed
}}

// notifyCallbacks 通知回调
func (p *{struct_name}) notifyCallbacks() {{
	p.mu.RLock()
	callbacks := make([]func([]map[string]interface{{}}), len(p.callbacks))
	copy(callbacks, p.callbacks)
	data := make([]map[string]interface{{}}, len(p.data))
	copy(data, p.data)
	p.mu.RUnlock()

	for _, callback := range callbacks {{
		go func(cb func([]map[string]interface{{}})) {{
			defer func() {{
				if r := recover(); r != nil {{
					p.logger.Printf("Callback panic: %v", r)
				}}
			}}()
			cb(data)
		}}(callback)
	}}
}}

// RegisterCallback 注册回调
func (p *{struct_name}) RegisterCallback(callback func([]map[string]interface{{}})) {{
	p.mu.Lock()
	defer p.mu.Unlock()
	p.callbacks = append(p.callbacks, callback)
}}

// Cleanup 清理资源
func (p *{struct_name}) Cleanup() {{
	p.mu.Lock()
	defer p.mu.Unlock()
	p.data = make([]map[string]interface{{}}, 0)
	p.callbacks = make([]func([]map[string]interface{{}}), 0)
	p.status = StatusCompleted
}}

// ExportResults 导出结果
func (p *{struct_name}) ExportResults() (string, error) {{
	p.mu.RLock()
	defer p.mu.RUnlock()
	data, err := json.MarshalIndent(p.data, "", "  ")
	return string(data), err
}}

// ValidateData 验证数据
func Validate{struct_name}Data(data map[string]interface{{}}) bool {{
	requiredFields := []string{{"id", "name", "type"}}
	for _, field := range requiredFields {{
		if _, exists := data[field]; !exists {{
			return false
		}}
	}}
	return true
}}

// {struct_name}Factory 工厂
type {struct_name}Factory struct {{
	instances map[string]*{struct_name}
	mu        sync.RWMutex
}}

// New{struct_name}Factory 创建工厂
func New{struct_name}Factory() *{struct_name}Factory {{
	return &{struct_name}Factory{{
		instances: make(map[string]*{struct_name}),
	}}
}}

// Create 创建实例
func (f *{struct_name}Factory) Create(name string, config {struct_name}Config) *{struct_name} {{
	f.mu.Lock()
	defer f.mu.Unlock()

	if instance, exists := f.instances[name]; exists {{
		return instance
	}}

	instance := New{struct_name}(config)
	f.instances[name] = instance
	return instance
}}

// GetInstance 获取实例
func (f *{struct_name}Factory) GetInstance(name string) *{struct_name} {{
	f.mu.RLock()
	defer f.mu.RUnlock()
	return f.instances[name]
}}

// RemoveInstance 移除实例
func (f *{struct_name}Factory) RemoveInstance(name string) bool {{
	f.mu.Lock()
	defer f.mu.Unlock()
	if _, exists := f.instances[name]; exists {{
		delete(f.instances, name)
		return true
	}}
	return false
}}

func main() {{
	config := {struct_name}Config{{
		Name:     "default",
		Value:    100,
		Enabled:  true,
		Priority: 1,
	}}

	processor := New{struct_name}(config)
	processor.Initialize()

	testData := []map[string]interface{{}}{{
		{{"id": 1, "name": "item1", "type": "test"}},
		{{"id": 2, "name": "item2", "type": "test"}},
	}}

	result, _ := processor.Process(testData)
	fmt.Printf("Result: %v\\n", result)

	processor.Cleanup()
}}
'''

def random_name(prefix, index):
    """生成随机名称"""
    suffix = ''.join(random.choices(string.ascii_uppercase, k=3))
    return f"{prefix}{index:03d}{suffix}"

def generate_description():
    """生成随机描述"""
    actions = ["处理", "管理", "控制", "分析", "计算", "验证", "转换", "优化"]
    objects = ["数据", "任务", "流程", "请求", "事件", "消息", "配置", "状态"]
    return f"{random.choice(actions)}{random.choice(objects)}的核心模块"

def generate_python_files(count):
    """生成Python文件"""
    os.makedirs(f"{BASE_DIR}/services", exist_ok=True)
    os.makedirs(f"{BASE_DIR}/models", exist_ok=True)
    os.makedirs(f"{BASE_DIR}/utils", exist_ok=True)

    for i in range(count):
        class_name = random_name("Processor", i)
        var_name = class_name.lower()
        module_name = f"processor_{i:03d}"
        description = generate_description()

        content = PYTHON_CLASS_TEMPLATE.format(
            module_name=module_name,
            class_name=class_name,
            var_name=var_name,
            description=description
        )

        if i % 3 == 0:
            filepath = f"{BASE_DIR}/services/{module_name}.py"
        elif i % 3 == 1:
            filepath = f"{BASE_DIR}/models/{module_name}.py"
        else:
            filepath = f"{BASE_DIR}/utils/{module_name}.py"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    print(f"Generated {count} Python files")

def generate_js_files(count):
    """生成JavaScript文件"""
    os.makedirs(f"{BASE_DIR}/frontend/src/modules", exist_ok=True)

    for i in range(count):
        class_name = random_name("Handler", i)
        module_name = f"handler_{i:03d}"
        description = generate_description()

        content = JS_CLASS_TEMPLATE.format(
            module_name=module_name,
            class_name=class_name,
            description=description
        )

        filepath = f"{BASE_DIR}/frontend/src/modules/{module_name}.js"
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    print(f"Generated {count} JavaScript files")

def generate_java_files(count):
    """生成Java文件"""
    os.makedirs(f"{BASE_DIR}/java_src/com/stress/test", exist_ok=True)

    for i in range(count):
        class_name = random_name("Service", i)
        description = generate_description()

        content = JAVA_CLASS_TEMPLATE.format(
            class_name=class_name,
            description=description
        )

        filepath = f"{BASE_DIR}/java_src/com/stress/test/{class_name}.java"
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    print(f"Generated {count} Java files")

def generate_go_files(count):
    """生成Go文件"""
    os.makedirs(f"{BASE_DIR}/go_src/pkg", exist_ok=True)

    for i in range(count):
        struct_name = random_name("Worker", i)
        description = generate_description()

        content = GO_FILE_TEMPLATE.format(
            struct_name=struct_name,
            description=description
        )

        filepath = f"{BASE_DIR}/go_src/pkg/{struct_name.lower()}.go"
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    print(f"Generated {count} Go files")

if __name__ == "__main__":
    print("Starting stress test file generation...")
    start_time = time.time()

    # 生成大量文件
    generate_python_files(100)
    generate_js_files(50)
    generate_java_files(30)
    generate_go_files(20)

    elapsed = time.time() - start_time
    print(f"\nTotal files generated in {elapsed:.2f} seconds")
    print(f"Files location: {BASE_DIR}")
