from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.schemas.response import PageResult, Result
from app.schemas.sys.dict import DictBody, DictItemBody
from app.db.session import get_db
from app.models.entities import SysDict, SysDictItem, SysUser
from app.services.dict_service import invalidate_dict_cache, load_dict, load_dict_item, query_all_dict_items
from app.utils.common import model_to_dict, new_id, paginate_query

router = APIRouter(prefix="/dict", tags=["数据字典"])


@router.get("/list")
def dict_list(
    pageNo: int = Query(1),
    pageSize: int = Query(10),
    dictName: Optional[str] = None,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    q = db.query(SysDict).filter(SysDict.del_flag == 0)
    if dictName:
        q = q.filter(SysDict.dict_name.like(f"%{dictName}%"))
    items, total = paginate_query(q, pageNo, pageSize)
    return Result.ok(PageResult.build([model_to_dict(d) for d in items], total, pageNo, pageSize).model_dump())


@router.get("/queryAllDictItems")
def query_all(db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    return Result.ok(query_all_dict_items(db))


@router.get("/getDictItems/{code}")
def get_dict_items(code: str, db: Session = Depends(get_db)):
    all_items = query_all_dict_items(db)
    return Result.ok(all_items.get(code, []))


@router.get("/loadDict/{code:path}")
def load_dict_api(
    code: str,
    keyword: Optional[str] = Query(None),
    pageNo: int = Query(1),
    pageSize: int = Query(10),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    items = load_dict(
        db,
        code,
        keyword=(keyword or "").strip(),
        page_no=pageNo,
        page_size=pageSize,
    )
    return Result.ok(items)


@router.get("/loadDictItem/{code:path}")
def load_dict_item_api(
    code: str,
    key: str = Query(...),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    return Result.ok(load_dict_item(db, code, key))


@router.post("/add")
def add_dict(body: DictBody, db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    d = SysDict(
        id=new_id(),
        dict_name=body.dictName,
        dict_code=body.dictCode,
        description=body.description,
        del_flag=0,
        create_by=user.username,
        create_time=datetime.now(),
    )
    db.add(d)
    db.commit()
    invalidate_dict_cache()
    return Result.ok(None, "添加成功！")


@router.post("/edit")
def edit_dict(body: DictBody, db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    d = db.query(SysDict).filter(SysDict.id == body.id).first()
    if not d:
        return Result.error("字典不存在")
    if body.dictName:
        d.dict_name = body.dictName
    if body.dictCode:
        d.dict_code = body.dictCode
    if body.description:
        d.description = body.description
    d.update_by = user.username
    d.update_time = datetime.now()
    db.commit()
    invalidate_dict_cache()
    return Result.ok(None, "修改成功！")


@router.delete("/delete")
def delete_dict(id: str = Query(...), db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    d = db.query(SysDict).filter(SysDict.id == id).first()
    if d:
        d.del_flag = 1
        db.commit()
        invalidate_dict_cache()
    return Result.ok(None, "删除成功!")


dict_item_router = APIRouter(prefix="/dictItem", tags=["字典项"])


@dict_item_router.get("/list")
def dict_item_list(
    dictId: str = Query(...),
    pageNo: int = Query(1),
    pageSize: int = Query(10),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    q = db.query(SysDictItem).filter(SysDictItem.dict_id == dictId)
    items, total = paginate_query(q.order_by(SysDictItem.sort_order), pageNo, pageSize)
    return Result.ok(PageResult.build([model_to_dict(i) for i in items], total, pageNo, pageSize).model_dump())


@dict_item_router.post("/add")
def add_item(body: DictItemBody, db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    item = SysDictItem(
        id=new_id(),
        dict_id=body.dictId,
        item_text=body.itemText,
        item_value=body.itemValue,
        description=body.description,
        sort_order=body.sortOrder,
        status=body.status,
        create_by=user.username,
        create_time=datetime.now(),
    )
    db.add(item)
    db.commit()
    invalidate_dict_cache()
    return Result.ok(None, "添加成功！")


@dict_item_router.post("/edit")
def edit_item(body: DictItemBody, db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    item = db.query(SysDictItem).filter(SysDictItem.id == body.id).first()
    if not item:
        return Result.error("字典项不存在")
    if body.itemText:
        item.item_text = body.itemText
    if body.itemValue:
        item.item_value = body.itemValue
    if body.sortOrder is not None:
        item.sort_order = body.sortOrder
    item.update_by = user.username
    item.update_time = datetime.now()
    db.commit()
    invalidate_dict_cache()
    return Result.ok(None, "修改成功！")


@dict_item_router.delete("/delete")
def delete_item(id: str = Query(...), db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    item = db.query(SysDictItem).filter(SysDictItem.id == id).first()
    if item:
        db.delete(item)
        db.commit()
        invalidate_dict_cache()
    return Result.ok(None, "删除成功!")
