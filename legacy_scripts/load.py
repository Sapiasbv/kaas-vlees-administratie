import pandas as pd,re
U="/root/.claude/uploads/409f47d1-0774-59fa-8af2-ef9852bec079/"
inv=pd.read_csv(U+"7f6ab1b1-inventory_export_vlees_admin_2026_11_04.csv",dtype=str,encoding='cp1252',low_memory=False)
main=inv[inv.Loc_Settings_LocID=="Main"].copy()
w=pd.read_excel(U+"71253dce-weegschaal_item_overzicht_2026_11_04.xlsx",header=None,dtype=str)
w.columns=['PLU','Artikel','Lev','Best','x4','x5','wp','prijs']
w=w.drop(columns=['x4','x5'])
w['PLU']=w.PLU.astype(int)
