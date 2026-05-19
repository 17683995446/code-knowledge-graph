package main

// FileIndexer - 文件索引器
// 为代码文件构建倒排索引，支持快速搜索

import (
	"fmt"
	"strings"
	"sync"
)

// FileInfo 文件信息结构体
type FileInfo struct {
	FilePath    string
	Language    string
	LineCount   int
	SymbolCount int
}

// IndexEntry 索引条目
type IndexEntry struct {
	Keyword string
	Files   []string
}

// FileIndexer 文件索引器
type FileIndexer struct {
	entries map[string]*IndexEntry
	mu      sync.RWMutex
}

// NewFileIndexer 创建新的文件索引器
func NewFileIndexer() *FileIndexer {
	return &FileIndexer{
		entries: make(map[string]*IndexEntry),
	}
}

// AddFile 添加文件到索引
func (indexer *FileIndexer) AddFile(filePath string, content string) {
	indexer.mu.Lock()
	defer indexer.mu.Unlock()

	words := tokenize(content)
	for _, word := range words {
		if entry, exists := indexer.entries[word]; exists {
			entry.Files = append(entry.Files, filePath)
		} else {
			indexer.entries[word] = &IndexEntry{
				Keyword: word,
				Files:   []string{filePath},
			}
		}
	}
}

// Search 搜索关键词
func (indexer *FileIndexer) Search(keyword string) []string {
	indexer.mu.RLock()
	defer indexer.mu.RUnlock()

	if entry, exists := indexer.entries[strings.ToLower(keyword)]; exists {
		return entry.Files
	}
	return nil
}

// GetStatistics 获取索引统计
func (indexer *FileIndexer) GetStatistics() map[string]int {
	indexer.mu.RLock()
	defer indexer.mu.RUnlock()

	stats := make(map[string]int)
	stats["total_keywords"] = len(indexer.entries)
	totalFiles := make(map[string]bool)
	for _, entry := range indexer.entries {
		for _, file := range entry.Files {
			totalFiles[file] = true
		}
	}
	stats["total_files"] = len(totalFiles)
	return stats
}

// tokenize 分词处理
func tokenize(content string) []string {
	words := strings.Fields(content)
	result := make([]string, 0, len(words))
	for _, word := range words {
		lower := strings.ToLower(word)
		if len(lower) > 2 {
			result = append(result, lower)
		}
	}
	return result
}

func main() {
	indexer := NewFileIndexer()
	sampleContent := "func hello world package main import fmt type struct interface"
	indexer.AddFile("main.go", sampleContent)

	results := indexer.Search("func")
	fmt.Printf("搜索 'func' 找到 %d 个文件\n", len(results))

	stats := indexer.GetStatistics()
	fmt.Printf("索引统计: %v\n", stats)
}
