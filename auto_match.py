"""Constraint-based allocation from the 300 EXISTING complete store folders.

A storefront is an indivisible existing store/template/product package. We do not
recombine products and layouts, and we never overwrite an assigned store.
The style-family labels below are intentionally conservative: multiple distinct
numbered templates share the same hero layout family and cannot be allocated to
one entity in strict mode. These are code-structure heuristics, not screenshots.
"""
from __future__ import annotations
import re, secrets

# Derived by examining 02-homepage.liquid in each of the 20 supplied groups.
STYLE_FAMILY = {
    1: ('editorial-campaign', '编辑式系列排版'),
    4: ('split-layout', '分屏式视觉排版'),
    5: ('ritual-layout', '叙事式场景排版'),
    6: ('launch-layout', '简约发布式排版'),
    10: ('mosaic-layout', '图片拼接布局'),
    19: ('work-layout', '专题工作室布局'),
    20: ('experimental-layout', '实验式版面布局'),
}

PRODUCT_FAMILY = {
    '短袖T恤':'上装','体恤':'上装','长袖T恤':'上装','Polo衫':'上装',
    '纽扣衬衫':'上装','背心':'上装',
    '连帽卫衣':'卫衣','圆领卫衣':'卫衣',
    '运动短裤':'裤装','束脚运动裤':'裤装',
    '棒球帽':'帽饰','针织帽':'帽饰',
    '袜子':'袜品','帆布托特包':'包袋','围裙':'围裙','毛巾':'家纺',
}

def identify_template(inner_path):
    """Return structured metadata only for exact supplied 20 x 15 folder format."""
    m=re.fullmatch(r'模板(\d+)/模板\1(.+)',(inner_path or '').strip('/'))
    if not m:return None
    group=int(m.group(1));cat=m.group(2)
    if not (1<=group<=20) or cat not in PRODUCT_FAMILY:return None
    style_code,style_name=STYLE_FAMILY.get(group,('hero-scene','标准Hero场景式布局'))
    return {'group':group,'category':cat,'product_family':PRODUCT_FAMILY[cat],
            'style_family':style_code,'style_name':style_name,
            'template_group':f'模板{group}'}

class AllocationError(ValueError):pass

def check_diversity(items):
    """Check combined existing and proposed store records for one legal entity."""
    errors=[];styles={};categories={};families={};groups={}
    for it in items:
        meta=identify_template(it['inner_path'])
        if not meta:
            errors.append(f"{it['code']} 模板目录无法识别，不能执行严格自动匹配")
            continue
        for field,seen,label in [('style_family',styles,'装修结构'),('category',categories,'商品品类'),
                                 ('product_family',families,'商品大类'),('group',groups,'装修模板组')]:
            key=meta[field]
            if key in seen:
                errors.append(f"{it['code']} 与 {seen[key]} 的{label}相同：{key}")
            else:seen[key]=it['code']
    return errors

def choose_candidates(connection,count:int,entity_id:str|None=None):
    if count not in (4,5):raise AllocationError('当前自动模式只支持一次分配4或5家店铺')
    existing=[]
    if entity_id:
        existing=[dict(r) for r in connection.execute('''SELECT s.id,s.code,t.inner_path FROM stores s
           JOIN templates t ON t.id=s.template_id WHERE s.entity_id=?''',(entity_id,))]
    errs=check_diversity(existing)
    if errs:raise AllocationError('当前主体已存在相似模板或品类：'+'；'.join(errs[:3]))
    used_styles={identify_template(x['inner_path'])['style_family'] for x in existing}
    used_families={identify_template(x['inner_path'])['product_family'] for x in existing}
    used_categories={identify_template(x['inner_path'])['category'] for x in existing}
    used_groups={identify_template(x['inner_path'])['group'] for x in existing}
    pool=[dict(r) for r in connection.execute('''SELECT s.id,s.code,s.label,t.code AS template_code,t.inner_path
             FROM stores s JOIN templates t ON t.id=s.template_id
             WHERE s.entity_id IS NULL AND NOT EXISTS (
               SELECT 1 FROM store_domains d WHERE d.store_id=s.id)
             ORDER BY s.code''')]
    for item in pool:item['meta']=identify_template(item['inner_path'])
    pool=[p for p in pool if p['meta'] and p['meta']['style_family'] not in used_styles
          and p['meta']['product_family'] not in used_families
          and p['meta']['category'] not in used_categories
          and p['meta']['group'] not in used_groups]
    if len(pool)<count:raise AllocationError('可用资源不足，无法保证同一主体下装修结构与商品类别均不同')
    # Shuffle for a fresh random proposal; backtracking ensures we do not
    # silently relax any of the hard constraints.
    rng=secrets.SystemRandom()
    rng.shuffle(pool)
    # Each pair of broad product-family/style-family may have several candidates;
    # random DFS is very fast at n<=5 and finds a strict solution if available.
    solution=[];steps=0
    def dfs(pos,styles,families,categories,groups):
        nonlocal steps
        if pos==count:return True
        if steps>250_000:return False
        for candidate in pool:
            if candidate in solution:continue
            m=candidate['meta']
            if (m['style_family'] in styles or m['product_family'] in families or
                    m['category'] in categories or m['group'] in groups):continue
            steps+=1
            solution.append(candidate)
            if dfs(pos+1,styles|{m['style_family']},families|{m['product_family']},
                   categories|{m['category']},groups|{m['group']}):return True
            solution.pop()
        return False
    if not dfs(0,used_styles,used_families,used_categories,used_groups):
        raise AllocationError('当前剩余资源不能满足4–5家店铺严格不相似的要求。未执行任何分配。')
    return solution
