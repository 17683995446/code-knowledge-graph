# Unicode和特殊字符测试
# 中文注释：这是一个测试文件
# 日本語コメント：テストファイルです
# 한국어 주석: 테스트 파일입니다
# Emoji: 🎉 🚀 💻 🔧 📊

class 中文类名:
    """中文类名的测试"""
    
    def 方法名(self, 参数一: str, 参数二: int = 0) -> dict:
        """
        这是一个中文方法
        """
        变量名 = "包含中文的字符串"
        return {"结果": 变量名}


class Ελληνικά:  # 希腊字母
    """Greek letters test"""
    
    def αβγδ(self):
        return "αβγδ"


class 日本語クラス:  # 日文类名
    """Japanese class name"""
    
    def メソッド(self):
        return "テスト"


class 한글클래스:  # 韩文类名
    """Korean class name"""
    
    def 메서드(self):
        return "테스트"


# 特殊字符变量名
_var_with_underscore = 1
__dunder_var__ = 2
CamelCaseVar = 3
mixedCase_Var123 = 4
_ = 5  # 单下划线
__ = 6  # 双下划线
