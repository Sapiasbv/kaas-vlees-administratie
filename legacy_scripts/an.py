exec(open('/tmp/claude-0/d/load.py').read())
pd.set_option('display.width',280,'display.max_columns',30,'display.max_rows',500,'display.max_colwidth',40)
main['Inv_Sku']=main.Inv_Sku.astype(str)
idx=main.set_index('Inv_Sku')
bulk=main[main.Inv_Sku.str.startswith('2024700')&main.Inv_Desc.str.match(r'(?i)\s*bulk',na=False)&~main.Inv_DepartID.str.contains('Kaas',na=False)].copy()
bulk['pv']=bulk.Inv_Part_Vendor.fillna('').str.strip()
def norm(s): return str(s).strip().lower() if isinstance(s,str) else ''
w['sku']=(200000+w.PLU).astype(str)
w['inRE']=w.sku.isin(idx.index)
for c in ['Inv_Desc','Inv_VendorID','Inv_Part_Vendor','Inv_DepartID','Inv_ClassID','Inv_Cost_Last','Inv_Loc_Price1','Inv_Quan']:
    w['re_'+c]=w.sku.map(idx[c]) if True else None
w['Best']=w.Best.fillna('').str.strip(); w['repv']=w.re_Inv_Part_Vendor.fillna('').str.strip()
