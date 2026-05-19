package com.demo.knowledgegraph;

/**
 * AnalysisResult - 分析结果数据类
 * 封装代码分析的结果数据
 */
public class AnalysisResult {

    private final int totalLines;
    private final int codeLines;
    private final int commentLines;
    private final int blankLines;
    private final int complexityScore;
    private final double commentRatio;
    private final double maintainabilityIndex;

    public AnalysisResult(int totalLines, int codeLines, int commentLines,
                          int blankLines, int complexityScore,
                          double commentRatio, double maintainabilityIndex) {
        this.totalLines = totalLines;
        this.codeLines = codeLines;
        this.commentLines = commentLines;
        this.blankLines = blankLines;
        this.complexityScore = complexityScore;
        this.commentRatio = commentRatio;
        this.maintainabilityIndex = maintainabilityIndex;
    }

    public String getSummary() {
        return String.format(
            "总行数: %d, 代码行: %d, 注释行: %d, 空行: %d, 复杂度: %d, 可维护性: %.1f",
            totalLines, codeLines, commentLines, blankLines,
            complexityScore, maintainabilityIndex
        );
    }

    public QualityGrade getQualityGrade() {
        if (maintainabilityIndex >= 80) return QualityGrade.EXCELLENT;
        if (maintainabilityIndex >= 60) return QualityGrade.GOOD;
        if (maintainabilityIndex >= 40) return QualityGrade.FAIR;
        return QualityGrade.POOR;
    }

    public int getTotalLines() { return totalLines; }
    public int getCodeLines() { return codeLines; }
    public int getCommentLines() { return commentLines; }
    public int getBlankLines() { return blankLines; }
    public int getComplexityScore() { return complexityScore; }
    public double getCommentRatio() { return commentRatio; }
    public double getMaintainabilityIndex() { return maintainabilityIndex; }

    /**
     * 代码质量等级枚举
     */
    public enum QualityGrade {
        EXCELLENT("优秀"),
        GOOD("良好"),
        FAIR("一般"),
        POOR("较差");

        private final String description;

        QualityGrade(String description) {
            this.description = description;
        }

        public String getDescription() {
            return description;
        }
    }
}
