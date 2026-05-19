"""
Deep Nesting Test - 深度嵌套测试
测试解析器对深度嵌套代码的处理能力
"""


class Level0:
    """Level 0 class"""
    
    class Level1:
        """Level 1 nested class"""
        
        class Level2:
            """Level 2 nested class"""
            
            class Level3:
                """Level 3 nested class"""
                
                class Level4:
                    """Level 4 nested class"""
                    
                    class Level5:
                        """Level 5 nested class"""
                        
                        def deep_method(self):
                            """深度嵌套的方法"""
                            if True:
                                if True:
                                    if True:
                                        if True:
                                            if True:
                                                if True:
                                                    if True:
                                                        if True:
                                                            if True:
                                                                if True:
                                                                    return "very deep"
                            return "not so deep"


def deeply_nested_function():
    """深度嵌套函数"""
    def level1():
        def level2():
            def level3():
                def level4():
                    def level5():
                        def level6():
                            def level7():
                                def level8():
                                    def level9():
                                        def level10():
                                            return "deepest"
                                        return level10()
                                    return level9()
                                return level8()
                            return level7()
                        return level6()
                    return level5()
                return level4()
            return level3()
        return level2()
    return level1()
