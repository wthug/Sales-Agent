import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from Tools.summary_retriever_tool import search_similar_summary
    print("successful")
except Exception as e:
    print(e)