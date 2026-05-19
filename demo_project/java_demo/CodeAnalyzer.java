package com.demo.knowledgegraph;

/**
 * CodeAnalyzer - 代码分析器
 * 提供代码度量和质量分析功能
 */
public class CodeAnalyzer {

    private int totalLines;
    private int codeLines;
    private int commentLines;
    private int blankLines;
    private int complexityScore;

    public CodeAnalyzer() {
        this.totalLines = 0;
        this.codeLines = 0;
        this.commentLines = 0;
        this.blankLines = 0;
        this.complexityScore = 0;
    }

    /**
     * 分析源代码文件
     */
    public AnalysisResult analyze(String sourceCode) {
        String[] lines = sourceCode.split("\n");
        this.totalLines = lines.length;

        for (String line : lines) {
            String trimmedLine = line.trim();
            if (trimmedLine.isEmpty()) {
                this.blankLines++;
            } else if (trimmedLine.startsWith("//") || trimmedLine.startsWith("/*") || trimmedLine.startsWith("*")) {
                this.commentLines++;
            } else {
                this.codeLines++;
                this.complexityScore += calculateLineComplexity(trimmedLine);
            }
        }

        return buildResult();
    }

    /**
     * 计算单行代码复杂度
     */
    private int calculateLineComplexity(String line) {
        int complexity = 0;
        if (line.contains("if")) complexity++;
        if (line.contains("else")) complexity++;
        if (line.contains("for")) complexity++;
        if (line.contains("while")) complexity++;
        if (line.contains("switch")) complexity += 2;
        if (line.contains("try")) complexity++;
        if (line.contains("catch")) complexity++;
        return complexity;
    }

    /**
     * 构建分析结果
     */
    private AnalysisResult buildResult() {
        double commentRatio = totalLines > 0 ? (double) commentLines / totalLines : 0;
        double maintainabilityIndex = calculateMaintainability(commentRatio);

        return new AnalysisResult(
            totalLines, codeLines, commentLines, blankLines,
            complexityScore, commentRatio, maintainabilityIndex
        );
    }

    /**
     * 计算可维护性指数
     */
    private double calculateMaintainability(double commentRatio) {
        double baseScore = 100.0;
        double complexityPenalty = complexityScore * 0.5;
        double commentBonus = commentRatio * 20.0;
        return Math.max(0, Math.min(100, baseScore - complexityPenalty + commentBonus));
    }

    /**
     * 重置分析器状态
     */
    public void reset() {
        this.totalLines = 0;
        this.codeLines = 0;
        this.commentLines = 0;
        this.blankLines = 0;
        this.complexityScore = 0;
    }

    public static void main(String[] args) {
        CodeAnalyzer analyzer = new CodeAnalyzer();
        String sampleCode = "public class Demo {\n// This is a comment\npublic void process() {\nif (true) {\nfor (int i = 0; i < 10; i++) {\n}\n}\n}\n}\n";
        AnalysisResult result = analyzer.analyze(sampleCode);
        System.out.println("分析完成: " + result.getSummary());
    }
}
